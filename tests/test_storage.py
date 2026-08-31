import json
import logging

import pytest

from core.models import Item
from core.storage import AzureBlobStorage, GCSStorage, S3Storage, Storage, create_storage


class FakeS3:
    def __init__(self):
        self.uploads = []

    def upload_file(self, filename, bucket, key):
        self.uploads.append((filename, bucket, key))


class FakeGCSBlob:
    def __init__(self, uploads, name):
        self.uploads = uploads
        self.name = name

    def upload_from_filename(self, filename):
        self.uploads.append((filename, self.name))


class FakeGCSBucket:
    def __init__(self, name, uploads):
        self.name = name
        self.uploads = uploads

    def blob(self, name):
        return FakeGCSBlob(self.uploads, name)


class FakeGCS:
    def __init__(self):
        self.uploads = []
        self.buckets = []

    def bucket(self, name):
        self.buckets.append(name)
        return FakeGCSBucket(name, self.uploads)


class FakeAzureBlob:
    def __init__(self, uploads, name):
        self.uploads = uploads
        self.name = name

    def upload_blob(self, data, overwrite=False):
        self.uploads.append((self.name, data.read(), overwrite))


class FakeAzureContainer:
    def __init__(self, uploads):
        self.uploads = uploads

    def get_blob_client(self, name):
        return FakeAzureBlob(self.uploads, name)


class FakeAzure:
    def __init__(self):
        self.uploads = []
        self.containers = []

    def get_container_client(self, name):
        self.containers.append(name)
        return FakeAzureContainer(self.uploads)


def test_storage_factory_defaults_to_filesystem(tmp_path):
    storage = create_storage(
        {"output_dir": str(tmp_path), "images_dir": str(tmp_path / "images")},
        logging.getLogger("test"),
    )

    assert type(storage) is Storage


def test_storage_factory_rejects_unknown_backend():
    with pytest.raises(ValueError, match="Unknown storage backend"):
        create_storage({"storage": {"backend": "tape"}}, logging.getLogger("test"))


def test_s3_storage_mirrors_items_and_comments(tmp_path):
    client = FakeS3()
    storage = S3Storage(
        output_dir=str(tmp_path / "output"),
        media_dir=str(tmp_path / "output" / "images"),
        logger=logging.getLogger("test"),
        bucket="archive",
        prefix="prod/social",
        client=client,
    )
    item = Item(
        id="post/1",
        source="twitter",
        target="@example",
        text="hello",
        comments=[{"id": "c1", "text": "reply"}],
    )

    item_path = storage.write_item(item)
    comments_path = storage.write_comments(item)

    assert json.loads(item_path.read_text(encoding="utf-8"))["text"] == "hello"
    assert comments_path is not None
    assert [upload[1:] for upload in client.uploads] == [
        ("archive", "prod/social/twitter/post_1.json"),
        ("archive", "prod/social/twitter/post_1_comments.json"),
    ]


def test_gcs_storage_mirrors_items_and_comments(tmp_path):
    client = FakeGCS()
    storage = GCSStorage(
        output_dir=str(tmp_path / "output"),
        media_dir=str(tmp_path / "output" / "images"),
        logger=logging.getLogger("test"),
        bucket="archive",
        prefix="prod/social",
        client=client,
    )
    item = Item(
        id="post/1",
        source="twitter",
        target="@example",
        text="hello",
        comments=[{"id": "c1", "text": "reply"}],
    )

    item_path = storage.write_item(item)
    comments_path = storage.write_comments(item)

    assert client.buckets == ["archive"]
    assert json.loads(item_path.read_text(encoding="utf-8"))["text"] == "hello"
    assert comments_path is not None
    assert [upload[1] for upload in client.uploads] == [
        "prod/social/twitter/post_1.json",
        "prod/social/twitter/post_1_comments.json",
    ]


def test_azure_blob_storage_mirrors_items_and_comments(tmp_path):
    client = FakeAzure()
    storage = AzureBlobStorage(
        output_dir=str(tmp_path / "output"),
        media_dir=str(tmp_path / "output" / "images"),
        logger=logging.getLogger("test"),
        container="archive",
        prefix="prod/social",
        client=client,
    )
    item = Item(
        id="post/1",
        source="twitter",
        target="@example",
        text="hello",
        comments=[{"id": "c1", "text": "reply"}],
    )

    item_path = storage.write_item(item)
    comments_path = storage.write_comments(item)

    assert client.containers == ["archive"]
    assert json.loads(item_path.read_text(encoding="utf-8"))["text"] == "hello"
    assert comments_path is not None
    assert [(upload[0], upload[2]) for upload in client.uploads] == [
        ("prod/social/twitter/post_1.json", True),
        ("prod/social/twitter/post_1_comments.json", True),
    ]


def test_azure_backend_requires_a_container():
    with pytest.raises(ValueError, match="storage.azure.container"):
        create_storage(
            {"storage": {"backend": "azure", "azure": {}}},
            logging.getLogger("test"),
        )


class _FakeMediaResponse:
    def __init__(self, data=b"", headers=None):
        self._data = data
        self.headers = headers or {}

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeMediaOpener:
    """Stands in for Storage._opener: HEAD gives content-type, GET gives bytes."""

    def __init__(self, data: bytes, content_type: str = "image/png"):
        self.data = data
        self.content_type = content_type

    def open(self, req_or_url, timeout=None):
        if hasattr(req_or_url, "get_method") and req_or_url.get_method() == "HEAD":
            return _FakeMediaResponse(headers={"Content-Type": self.content_type})
        return _FakeMediaResponse(data=self.data)


def test_download_media_names_file_by_content_hash(tmp_path):
    import hashlib
    from pathlib import Path

    storage = Storage(str(tmp_path / "out"), str(tmp_path / "media"), logging.getLogger("test"))
    data = b"hello-world"
    storage._opener = _FakeMediaOpener(data)

    path = storage.download_media("https://example.test/a.png", "twitter:1", 0)

    assert Path(path).name == f"{hashlib.sha256(data).hexdigest()}.png"


def test_download_media_dedups_identical_content_across_accounts(tmp_path):
    from pathlib import Path

    storage = Storage(str(tmp_path / "out"), str(tmp_path / "media"), logging.getLogger("test"))
    storage._opener = _FakeMediaOpener(b"same-bytes")

    p1 = storage.download_media("https://example.test/a.png", "twitter:1", 0)
    p2 = storage.download_media("https://example.test/b.png", "reddit:2", 0)

    assert p1 == p2
    assert len(list((tmp_path / "media").glob("*.png"))) == 1


def test_download_media_keeps_distinct_content_separate(tmp_path):
    storage = Storage(str(tmp_path / "out"), str(tmp_path / "media"), logging.getLogger("test"))

    storage._opener = _FakeMediaOpener(b"content-a")
    p1 = storage.download_media("https://example.test/a.png", "twitter:1", 0)

    storage._opener = _FakeMediaOpener(b"content-b")
    p2 = storage.download_media("https://example.test/b.png", "twitter:1", 1)

    assert p1 != p2
    assert len(list((tmp_path / "media").glob("*.png"))) == 2
