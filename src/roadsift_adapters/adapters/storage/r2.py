from __future__ import annotations

import mimetypes
from pathlib import Path, PurePosixPath
from typing import BinaryIO

import boto3
from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import ClientError

from roadsift_adapters.ports.object_store import (
    ObjectConflictError,
    ObjectHead,
    ObjectNotFoundError,
    ObjectStore,
    UnsafeObjectKeyError,
)


def _safe_key(key: str) -> str:
    candidate = PurePosixPath(key.strip("/"))
    if not key or key.startswith("/") or ".." in candidate.parts or str(candidate) in {"", "."}:
        raise UnsafeObjectKeyError(f"unsafe object key: {key!r}")
    return str(candidate)


class R2ObjectStore(ObjectStore):
    """Cloudflare R2 adapter using its S3-compatible API.

    New implementation for RoadSift. Provider credentials live only in adapter construction
    and are never serialized into jobs or artifact metadata.
    """

    def __init__(
        self,
        *,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        region: str = "auto",
        presign_ttl_seconds: int = 300,
        client: BaseClient | None = None,
    ) -> None:
        self.bucket = bucket
        self.presign_ttl_seconds = presign_ttl_seconds
        self.client = client or boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "adaptive"}),
        )

    def _put_args(
        self, key: str, content_type: str | None, metadata: dict[str, str] | None
    ) -> dict:
        args: dict = {"Bucket": self.bucket, "Key": _safe_key(key)}
        if content_type:
            args["ContentType"] = content_type
        if metadata:
            args["Metadata"] = {str(k): str(v) for k, v in metadata.items()}
        return args

    def put_file(
        self,
        source: str | Path,
        *,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        if_absent: bool = False,
    ) -> ObjectHead:
        source_path = Path(source)
        guessed = content_type or mimetypes.guess_type(source_path.name)[0] or "application/octet-stream"
        with source_path.open("rb") as stream:
            return self.put_stream(
                stream,
                key=key,
                content_type=guessed,
                metadata=metadata,
                if_absent=if_absent,
            )

    def put_stream(
        self,
        stream: BinaryIO,
        *,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        if_absent: bool = False,
    ) -> ObjectHead:
        safe = _safe_key(key)
        if if_absent and self.exists(safe):
            raise ObjectConflictError(f"object already exists: {safe}")
        args = self._put_args(safe, content_type, metadata)
        args["Body"] = stream
        self.client.put_object(**args)
        return self.head(safe)

    def head(self, key: str) -> ObjectHead:
        safe = _safe_key(key)
        try:
            response = self.client.head_object(Bucket=self.bucket, Key=safe)
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                raise ObjectNotFoundError(safe) from exc
            raise
        return ObjectHead(
            key=safe,
            size=int(response.get("ContentLength", 0)),
            etag=str(response.get("ETag", "")).strip('"') or None,
            content_type=response.get("ContentType"),
            metadata={str(k): str(v) for k, v in response.get("Metadata", {}).items()},
        )

    def exists(self, key: str) -> bool:
        try:
            self.head(key)
            return True
        except ObjectNotFoundError:
            return False

    def download_file(self, key: str, destination: str | Path) -> Path:
        safe = _safe_key(key)
        target = Path(destination)
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_suffix(target.suffix + ".partial")
        self.client.download_file(self.bucket, safe, str(partial))
        partial.replace(target)
        return target

    def presign_get(self, key: str, ttl_seconds: int | None = None) -> str:
        safe = _safe_key(key)
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": safe},
            ExpiresIn=ttl_seconds or self.presign_ttl_seconds,
        )
