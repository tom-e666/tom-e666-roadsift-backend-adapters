from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from roadsift_adapters.ports.executor import ComputeExecutor, JobHandle, JobResult, JobSpec, JobStatus


class KaggleExecutorError(RuntimeError):
    pass


class KaggleCliMissingError(KaggleExecutorError):
    pass


class KaggleCredentialError(KaggleExecutorError):
    pass


class KaggleCommandError(KaggleExecutorError):
    pass


_WORKER = r'''from __future__ import annotations
import json, os, subprocess, sys, traceback
from pathlib import Path
ROOT = Path(__file__).resolve().parent
JOB = json.loads((ROOT / "job.json").read_text(encoding="utf-8"))
OUT = Path("/kaggle/working")

def main():
    result = OUT / "job_result.json"
    env = os.environ.copy()
    env.update({str(k): str(v) for k, v in JOB.get("environment", {}).items()})
    try:
        command = [sys.executable if i == 0 and v in {"python", "python3"} else v for i, v in enumerate(JOB["command"])]
        completed = subprocess.run(command, cwd=ROOT / "project", env=env, check=False)
        payload = {"job_id": JOB["job_id"], "status": "COMPLETED" if completed.returncode == 0 else "FAILED", "exit_code": completed.returncode}
        result.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return completed.returncode
    except Exception as exc:
        result.write_text(json.dumps({"job_id": JOB.get("job_id", "unknown"), "status": "FAILED", "exit_code": 1, "error": str(exc)}, indent=2) + "\n", encoding="utf-8")
        traceback.print_exc()
        return 1
if __name__ == "__main__": raise SystemExit(main())
'''


class KaggleExecutor(ComputeExecutor):
    """Generic Kaggle CLI compute adapter.

    Refactored from P-021 src/rav05/execution/kaggle.py at legacy commit
    22cb0e700da11d0bdb4c14ed42959e327e1d397c.

    Preserved rules:
    - Kaggle is ephemeral compute, never source of truth.
    - JobSpec remains credential-free.
    - status/log/collect are provider operations behind one port.

    Changed:
    - no hard dependency on RAV-05 smoke scripts;
    - project snapshot is caller-selected;
    - adapter can be reused by RoadSift mining jobs.
    """

    executor_name = "kaggle"

    def __init__(
        self,
        *,
        kernel_slug: str,
        project_root: str | Path,
        accelerator: str | None = None,
        kaggle_executable: str = "kaggle",
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        which: Callable[[str], str | None] = shutil.which,
        environ: dict[str, str] | None = None,
    ) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", kernel_slug):
            raise ValueError("kernel_slug must be owner/kernel-slug")
        self.kernel_slug = kernel_slug
        self.project_root = Path(project_root).resolve()
        self.accelerator = accelerator
        self.kaggle_executable = kaggle_executable
        self._run = run
        self._which = which
        self._environ = dict(os.environ if environ is None else environ)

    def _ensure_cli(self) -> None:
        if self._which(self.kaggle_executable) is None:
            raise KaggleCliMissingError("Kaggle CLI not found; install the official kaggle package")

    def _run_cli(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        self._ensure_cli()
        completed = self._run(command, capture_output=True, text=True, check=False, env=self._environ)
        if completed.returncode == 0:
            return completed
        detail = f"{completed.stdout}\n{completed.stderr}".lower()
        if any(x in detail for x in ("unauthorized", "authentication", "credential", "api token")):
            raise KaggleCredentialError("Kaggle authentication unavailable or rejected")
        raise KaggleCommandError(f"Kaggle command failed ({completed.returncode}): {' '.join(command)}")

    def _metadata(self, spec: JobSpec) -> dict:
        slug = self.kernel_slug.split("/", 1)[1]
        gpu = bool(self.accelerator and self.accelerator.lower() not in {"cpu", "none"})
        datasets = spec.metadata.get("kaggle_dataset_sources", [])
        if not isinstance(datasets, list) or not all(isinstance(x, str) and "/" in x for x in datasets):
            raise ValueError("metadata.kaggle_dataset_sources must contain owner/dataset-slug strings")
        return {
            "id": self.kernel_slug,
            "title": slug.replace("-", " "),
            "code_file": "worker.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": bool(spec.metadata.get("kaggle_private", True)),
            "enable_gpu": gpu,
            "enable_internet": bool(spec.metadata.get("kaggle_enable_internet", False)),
            "machine_shape": self.accelerator if gpu else "",
            "dataset_sources": datasets,
            "competition_sources": [],
            "kernel_sources": [],
            "model_sources": [],
        }

    def prepare_bundle(self, spec: JobSpec, work_dir: str | Path) -> Path:
        bundle = Path(work_dir).resolve() / "job_bundle"
        if bundle.exists():
            shutil.rmtree(bundle)
        bundle.mkdir(parents=True)
        if not self.project_root.is_dir():
            raise FileNotFoundError(self.project_root)
        shutil.copytree(
            self.project_root,
            bundle / "project",
            ignore=shutil.ignore_patterns(".git", ".venv", "__pycache__", "*.pyc", ".env", ".runtime"),
        )
        (bundle / "job.json").write_text(spec.model_dump_json(indent=2) + "\n", encoding="utf-8")
        (bundle / "kernel-metadata.json").write_text(json.dumps(self._metadata(spec), indent=2) + "\n", encoding="utf-8")
        (bundle / "worker.py").write_text(_WORKER, encoding="utf-8")
        return bundle

    def submit(self, spec: JobSpec, work_dir: str | Path) -> JobHandle:
        bundle = self.prepare_bundle(spec, work_dir)
        cmd = [self.kaggle_executable, "kernels", "push", "-p", str(bundle)]
        if self.accelerator and self.accelerator.lower() not in {"cpu", "none"}:
            cmd.extend(["--accelerator", self.accelerator])
        self._run_cli(cmd)
        return JobHandle(job_id=spec.job_id, executor=self.executor_name, provider_id=self.kernel_slug, work_dir=str(bundle))

    def status(self, handle: JobHandle) -> JobStatus:
        if handle.provider_id != self.kernel_slug:
            raise ValueError("JobHandle provider_id does not match executor kernel")
        result = self._run_cli([self.kaggle_executable, "kernels", "status", self.kernel_slug])
        text = f"{result.stdout}\n{result.stderr}".lower()
        if "queued" in text:
            return JobStatus.QUEUED
        if "running" in text:
            return JobStatus.RUNNING
        if any(x in text for x in ("error", "failed", "cancelled", "canceled")):
            return JobStatus.FAILED
        if "complete" in text:
            return JobStatus.COMPLETED
        return JobStatus.UNKNOWN

    def collect(self, handle: JobHandle, output_dir: str | Path) -> JobResult:
        if handle.provider_id != self.kernel_slug:
            raise ValueError("JobHandle provider_id does not match executor kernel")
        output = Path(output_dir).resolve()
        output.mkdir(parents=True, exist_ok=True)
        self._run_cli([self.kaggle_executable, "kernels", "output", self.kernel_slug, "-p", str(output), "-o"])
        result_files = sorted(output.rglob("job_result.json"))
        if not result_files:
            raise FileNotFoundError("Kaggle output missing job_result.json")
        payload = json.loads(result_files[0].read_text(encoding="utf-8"))
        spec = JobSpec.model_validate_json((Path(handle.work_dir) / "job.json").read_text(encoding="utf-8"))
        artifacts = {name: str(output / relative) for name, relative in spec.outputs.items() if (output / relative).exists()}
        return JobResult(
            job_id=handle.job_id,
            status=JobStatus(str(payload.get("status", "UNKNOWN"))),
            output_dir=str(output),
            exit_code=payload.get("exit_code"),
            artifacts=artifacts,
        )
