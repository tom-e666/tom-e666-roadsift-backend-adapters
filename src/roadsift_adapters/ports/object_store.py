from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


class ObjectStoreError(RuntimeError):
    pass


class ObjectNotFoundError(ObjectStoreError):
    pass


class ObjectConflictError(ObjectStoreError):
    pass


class UnsafeObjectKeyError(ObjectStoreError):
    pass


@dataclass(frozen=True, slots=True)
class ObjectHead:
    key: str
    size: int
    etag: str | None
    content_type: str | None
    metadata: dict[str, str]


class ObjectStore(ABC):
    """Provider-neutral byte store.

    DB rows may keep object keys/URIs; large bytes stay outside Postgres.
    """

    @abstractmethod
    def put_file(
        self,
        source: str | Path,
        *,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        if_absent: bool = False,
    ) -> ObjectHead: ...

    @abstractmethod
    def put_stream(
        self,
        stream: BinaryIO,
        *,
        key: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        if_absent: bool = False,
    ) -> ObjectHead: ...

    @abstractmethod
    def head(self, key: str) -> ObjectHead: ...

    @abstractmethod
    def download_file(self, key: str, destination: str | Path) -> Path: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def presign_get(self, key: str, ttl_seconds: int | None = None) -> str: ...
