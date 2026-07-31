"""Pluggable output writers and the media downloader.

Records are written under ``output/<source>/<id>.json`` so sources stay tidy and
filenames never collide. The media downloader is the original ``scraper.py``
image downloader, generalized to any media type and reused by every connector.

The default ``filesystem`` backend behaves exactly as before. The optional
``s3`` backend keeps that local cache (so the dashboard remains browsable) and
mirrors every record, comment sidecar, and downloaded media object to an
S3-compatible bucket. The ``gcs`` backend provides the same local-first
mirroring behavior for Google Cloud Storage. The ``azure`` backend does the
same for Azure Blob Storage.
"""

from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.request
from pathlib import Path
from typing import Any, Optional

from .models import Item

_EXT_MAP = {
    "image/gif": "gif",
    "image/webp": "webp",
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "video/mp4": "mp4",
    "video/webm": "webm",
    "video/ogg": "ogv",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
}

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def _safe(name: str) -> str:
    """Make an id safe to use as a filename component."""
    return _SAFE_NAME.sub("_", name)[:120] or "item"


class Storage:
    """Filesystem storage for normalized items and their media."""

    def __init__(self, output_dir: str, media_dir: str, logger: logging.Logger):
        self.output_dir = Path(output_dir)
        self.media_dir = Path(media_dir)
        self.logger = logger
        self.media_dir.mkdir(parents=True, exist_ok=True)
        self._opener = self._build_opener()

    def _build_opener(self):
        context = ssl._create_unverified_context()
        handler = urllib.request.HTTPSHandler(context=context)
        opener = urllib.request.build_opener(handler)
        opener.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "Chrome/91.0.4472.124 Safari/537.36",
            ),
            ("Accept", "*/*"),
        ]
        return opener

    # --- media ---
    def download_media(self, url: str, item_uid: str, index: int = 0) -> Optional[str]:
        """Download ``url`` into the media dir, naming by uid + index.

        Extension is taken from the Content-Type header, falling back to the URL.
        Returns the local path, or None on failure. Existing files are reused.
        """
        try:
            try:
                req = urllib.request.Request(url, method="HEAD")
                with self._opener.open(req, timeout=15) as resp:
                    content_type = (
                        resp.headers.get("Content-Type", "").split(";")[0].strip().lower()
                    )
            except Exception:
                content_type = ""

            ext = _EXT_MAP.get(content_type)
            if not ext:
                ext_part = url.split("?")[0].rsplit(".", 1)[-1]
                ext = ext_part[:4].lower() if len(ext_part) <= 4 and ext_part.isalnum() else "bin"

            filename = f"{_safe(item_uid)}_{index}.{ext}"
            filepath = self.media_dir / filename

            if filepath.exists():
                if filepath.suffix[1:] == ext:
                    self.logger.debug("Media already exists: %s", filename)
                    return str(filepath)
                filepath.unlink()  # extension changed; re-download

            with self._opener.open(url, timeout=30) as resp, open(filepath, "wb") as out:
                out.write(resp.read())
            self.logger.info("Downloaded media: %s", filename)
            return str(filepath)
        except Exception as e:
            self.logger.warning("Failed to download media from %s: %s", url, e)
            return None

    # --- records ---
    def write_item(self, item: Item) -> Path:
        """Write a single item's normalized JSON to output/<source>/<id>.json."""
        dest_dir = self.output_dir / _safe(item.source)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"{_safe(item.id)}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(item.to_dict(), f, indent=2, ensure_ascii=False)
        return path

    def write_comments(self, item: Item) -> Optional[Path]:
        """Write an item's comments to a sidecar file, if any."""
        if not item.comments:
            return None
        dest_dir = self.output_dir / _safe(item.source)
        dest_dir.mkdir(parents=True, exist_ok=True)
        path = dest_dir / f"{_safe(item.id)}_comments.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(item.comments, f, indent=2, ensure_ascii=False)
        self.logger.info("Saved %d comments for %s", len(item.comments), item.uid)
        return path


class S3Storage(Storage):
    """Filesystem cache mirrored to AWS S3 or an S3-compatible service."""

    def __init__(
        self,
        output_dir: str,
        media_dir: str,
        logger: logging.Logger,
        bucket: str,
        prefix: str = "",
        endpoint_url: str | None = None,
        region: str | None = None,
        client: Any = None,
    ):
        if not bucket:
            raise ValueError("storage.s3.bucket is required for the s3 backend")
        super().__init__(output_dir, media_dir, logger)
        if client is None:
            try:
                import boto3
            except ImportError as exc:
                raise RuntimeError(
                    "The s3 backend requires boto3. Install it with: pip install boto3"
                ) from exc
            client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                region_name=region or None,
            )
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")

    def _key(self, relative: str) -> str:
        relative = relative.replace("\\", "/").lstrip("/")
        return f"{self.prefix}/{relative}" if self.prefix else relative

    def _upload(self, path: Path, relative: str) -> None:
        key = self._key(relative)
        self.client.upload_file(str(path), self.bucket, key)
        self.logger.info("Uploaded s3://%s/%s", self.bucket, key)

    def download_media(self, url: str, item_uid: str, index: int = 0) -> Optional[str]:
        local = super().download_media(url, item_uid, index)
        if local:
            path = Path(local)
            self._upload(path, f"images/{path.name}")
        return local

    def write_item(self, item: Item) -> Path:
        path = super().write_item(item)
        self._upload(path, f"{_safe(item.source)}/{path.name}")
        return path

    def write_comments(self, item: Item) -> Optional[Path]:
        path = super().write_comments(item)
        if path:
            self._upload(path, f"{_safe(item.source)}/{path.name}")
        return path


class GCSStorage(Storage):
    """Filesystem cache mirrored to a native Google Cloud Storage bucket."""

    def __init__(
        self,
        output_dir: str,
        media_dir: str,
        logger: logging.Logger,
        bucket: str,
        prefix: str = "",
        project: str | None = None,
        client: Any = None,
    ):
        if not bucket:
            raise ValueError("storage.gcs.bucket is required for the gcs backend")
        super().__init__(output_dir, media_dir, logger)
        if client is None:
            try:
                from google.cloud import storage as gcs_storage
            except ImportError as exc:
                raise RuntimeError(
                    "The gcs backend requires google-cloud-storage. Install it with: "
                    "pip install google-cloud-storage"
                ) from exc
            client = gcs_storage.Client(project=project or None)
        self.client = client
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._bucket = client.bucket(bucket)

    def _key(self, relative: str) -> str:
        relative = relative.replace("\\", "/").lstrip("/")
        return f"{self.prefix}/{relative}" if self.prefix else relative

    def _upload(self, path: Path, relative: str) -> None:
        key = self._key(relative)
        self._bucket.blob(key).upload_from_filename(str(path))
        self.logger.info("Uploaded gs://%s/%s", self.bucket, key)

    def download_media(self, url: str, item_uid: str, index: int = 0) -> Optional[str]:
        local = super().download_media(url, item_uid, index)
        if local:
            path = Path(local)
            self._upload(path, f"images/{path.name}")
        return local

    def write_item(self, item: Item) -> Path:
        path = super().write_item(item)
        self._upload(path, f"{_safe(item.source)}/{path.name}")
        return path

    def write_comments(self, item: Item) -> Optional[Path]:
        path = super().write_comments(item)
        if path:
            self._upload(path, f"{_safe(item.source)}/{path.name}")
        return path


class AzureBlobStorage(Storage):
    """Filesystem cache mirrored to a native Azure Blob Storage container."""

    def __init__(
        self,
        output_dir: str,
        media_dir: str,
        logger: logging.Logger,
        container: str,
        prefix: str = "",
        connection_string: str | None = None,
        client: Any = None,
    ):
        if not container:
            raise ValueError("storage.azure.container is required for the azure backend")
        super().__init__(output_dir, media_dir, logger)
        if client is None:
            if not connection_string:
                raise ValueError(
                    "storage.azure.connection_string is required for the azure backend"
                )
            try:
                from azure.storage.blob import BlobServiceClient
            except ImportError as exc:
                raise RuntimeError(
                    "The azure backend requires azure-storage-blob. Install it with: "
                    "pip install azure-storage-blob"
                ) from exc
            client = BlobServiceClient.from_connection_string(connection_string)
        self.client = client
        self.container = container
        self.prefix = prefix.strip("/")
        self._container = client.get_container_client(container)

    def _key(self, relative: str) -> str:
        relative = relative.replace("\\", "/").lstrip("/")
        return f"{self.prefix}/{relative}" if self.prefix else relative

    def _upload(self, path: Path, relative: str) -> None:
        key = self._key(relative)
        with path.open("rb") as data:
            self._container.get_blob_client(key).upload_blob(data, overwrite=True)
        self.logger.info("Uploaded azure://%s/%s", self.container, key)

    def download_media(self, url: str, item_uid: str, index: int = 0) -> Optional[str]:
        local = super().download_media(url, item_uid, index)
        if local:
            path = Path(local)
            self._upload(path, f"images/{path.name}")
        return local

    def write_item(self, item: Item) -> Path:
        path = super().write_item(item)
        self._upload(path, f"{_safe(item.source)}/{path.name}")
        return path

    def write_comments(self, item: Item) -> Optional[Path]:
        path = super().write_comments(item)
        if path:
            self._upload(path, f"{_safe(item.source)}/{path.name}")
        return path


def create_storage(config: dict, logger: logging.Logger) -> Storage:
    """Build the configured storage backend.

    ``storage.backend`` accepts ``filesystem`` (default), ``s3``, ``gcs``, or
    ``azure``. Legacy top-level ``output_dir``/``images_dir`` settings remain
    supported.
    """
    storage_config = config.get("storage", {}) or {}
    backend = str(storage_config.get("backend", "filesystem")).lower()
    output_dir = storage_config.get(
        "output_dir", config.get("output_dir", "./output")
    )
    media_dir = storage_config.get(
        "images_dir", config.get("images_dir", "./output/images")
    )
    if backend == "filesystem":
        return Storage(output_dir, media_dir, logger)
    if backend == "s3":
        s3 = storage_config.get("s3", {}) or {}
        return S3Storage(
            output_dir=output_dir,
            media_dir=media_dir,
            logger=logger,
            bucket=s3.get("bucket", ""),
            prefix=s3.get("prefix", ""),
            endpoint_url=s3.get("endpoint_url"),
            region=s3.get("region"),
        )
    if backend == "gcs":
        gcs = storage_config.get("gcs", {}) or {}
        return GCSStorage(
            output_dir=output_dir,
            media_dir=media_dir,
            logger=logger,
            bucket=gcs.get("bucket", ""),
            prefix=gcs.get("prefix", ""),
            project=gcs.get("project"),
        )
    if backend == "azure":
        azure = storage_config.get("azure", {}) or {}
        return AzureBlobStorage(
            output_dir=output_dir,
            media_dir=media_dir,
            logger=logger,
            container=azure.get("container", ""),
            prefix=azure.get("prefix", ""),
            connection_string=azure.get("connection_string"),
        )
    raise ValueError(
        f"Unknown storage backend '{backend}'. Expected: filesystem, s3, gcs, or azure"
    )
