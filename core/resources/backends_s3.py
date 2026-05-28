"""S3 / S3-compatible ArtifactBackend.

Optional dependency: ``s3fs``.  Works with AWS S3, MinIO, and any
S3-compatible object store (Ceph, DigitalOcean Spaces, etc.).
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Mapping, Optional

from .backends import ArtifactBackend, DataRef


class S3ArtifactBackend(ArtifactBackend):
    """Store artifacts in S3 or an S3-compatible object store.

    ``write(name, data)`` uploads to ``s3://bucket/prefix/name`` and returns a
    ``DataRef`` with ``backend="s3"``.  ``read(ref)`` fetches the object back.

    Optional dependencies: ``s3fs``.
    """

    def __init__(
        self,
        *,
        bucket: str = "nsgablack-artifacts",
        prefix: str = "l0_artifacts",
        endpoint_url: str = "",
        access_key: str = "",
        secret_key: str = "",
        region: str = "",
    ) -> None:
        self.bucket = str(bucket).strip("/")
        self.prefix = str(prefix).strip("/")
        self.endpoint_url = str(endpoint_url)
        self.access_key = str(access_key)
        self.secret_key = str(secret_key)
        self.region = str(region)
        self._fs = None

    @property
    def fs(self):
        if self._fs is None:
            try:
                import s3fs
            except ImportError as exc:
                raise ImportError(
                    "S3ArtifactBackend requires s3fs.  pip install s3fs"
                ) from exc
            kwargs: dict = {"key": self.access_key, "secret": self.secret_key}
            if self.endpoint_url:
                kwargs["endpoint_url"] = self.endpoint_url
            if self.region:
                kwargs["region_name"] = self.region
            self._fs = s3fs.S3FileSystem(**kwargs)
        return self._fs

    def _s3_path(self, name: str) -> str:
        clean = str(name).strip().replace("\\", "/").lstrip("/")
        return f"{self.bucket}/{self.prefix}/{clean}"

    def put_bytes(
        self,
        name: str,
        data: bytes,
        *,
        kind: str = "artifact",
        media_type: str = "application/octet-stream",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> DataRef:
        s3_path = self._s3_path(name)
        self.fs.mkdirs(f"{self.bucket}/{self.prefix}", exist_ok=True)
        with self.fs.open(s3_path, "wb") as f:
            f.write(bytes(data))

        checksum = hashlib.sha256(bytes(data)).hexdigest()
        meta = {
            "uri": f"s3://{s3_path}",
            "kind": str(kind),
            "backend": "s3",
            "media_type": str(media_type),
            "checksum": checksum,
            "size_bytes": len(data),
            "metadata": dict(metadata or {}),
            "created_at": time.time(),
        }
        meta_path = s3_path + ".meta.json"
        with self.fs.open(meta_path, "w") as f:
            f.write(json.dumps(meta, ensure_ascii=False, indent=2))

        return DataRef(
            uri=f"s3://{s3_path}",
            kind=str(kind),
            backend="s3",
            media_type=str(media_type),
            checksum=checksum,
            size_bytes=len(data),
            metadata=dict(metadata or {}),
        )

    def get_bytes(self, ref: DataRef | Mapping[str, Any] | str) -> bytes:
        uri = str(ref) if isinstance(ref, str) else (
            ref.get("uri", "") if isinstance(ref, Mapping) else str(getattr(ref, "uri", ""))
        )
        s3_path = str(uri).removeprefix("s3://").lstrip("/")
        with self.fs.open(s3_path, "rb") as f:
            return f.read()
