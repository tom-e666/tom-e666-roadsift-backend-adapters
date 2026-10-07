from __future__ import annotations

import re
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Inherited behaviour from P-021 src/rav05/execution/models.py: provider-neutral job
# contract and rejection of credential-like fields inside serializable JobSpec.
_SECRET_KEY = re.compile(
    r"(?i)(?:^|[_-])(token|secret|password|credential|api[_-]?key|kaggle[_-]?key)(?:$|[_-])"
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


def _reject_secret_keys(value: Any, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key)
            if _SECRET_KEY.search(key_text):
                raise ValueError(f"{path}.{key_text} looks credential-like; keep secrets outside JobSpec")
            _reject_secret_keys(child, f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_secret_keys(child, f"{path}[{index}]")


class JobSpec(StrictModel):
    job_id: str = Field(min_length=1)
    job_type: str = Field(min_length=1)
    command: list[str] = Field(min_length=1)
    inputs: dict[str, str] = Field(default_factory=dict)
    outputs: dict[str, str] = Field(default_factory=dict)
    environment: dict[str, str] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_portability(self) -> "JobSpec":
        for field_name in ("inputs", "outputs", "environment", "config", "metadata"):
            _reject_secret_keys(getattr(self, field_name), field_name)
        for token in self.command:
            normalized = token.lstrip("-").replace("=", "_")
            if _SECRET_KEY.search(normalized):
                raise ValueError("command contains credential-like argument")
        for name, relative in self.outputs.items():
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"output {name!r} must be a safe relative path")
        return self


class JobHandle(StrictModel):
    job_id: str
    executor: str
    provider_id: str
    work_dir: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobResult(StrictModel):
    job_id: str
    status: JobStatus
    output_dir: str
    exit_code: int | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComputeExecutor(ABC):
    @abstractmethod
    def submit(self, spec: JobSpec, work_dir: str | Path) -> JobHandle: ...

    @abstractmethod
    def status(self, handle: JobHandle) -> JobStatus: ...

    @abstractmethod
    def collect(self, handle: JobHandle, output_dir: str | Path) -> JobResult: ...
