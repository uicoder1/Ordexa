import os
import shutil
import io
from abc import ABC, abstractmethod
from datetime import datetime
from typing import BinaryIO, Optional
from fastapi import UploadFile, HTTPException

from app.config import settings

class StorageProvider(ABC):
    """
    Abstract interface for report file storage.
    Enables pluggable Local and Cloud Object Storage (S3 / R2 / GCS).
    """

    @abstractmethod
    def save_file(self, organization_id: str, upload_file: UploadFile) -> str:
        """Saves an uploaded file and returns its storage reference path."""
        pass

    @abstractmethod
    def get_absolute_path(self, rel_storage_path: str) -> str:
        """Returns the local filesystem path if available, or a downloaded local cache path."""
        pass

    @abstractmethod
    def open_stream(self, rel_storage_path: str) -> BinaryIO:
        """Returns a readable binary stream for the file."""
        pass

    @abstractmethod
    def delete_file(self, rel_storage_path: str) -> bool:
        """Deletes a file from storage."""
        pass

    @abstractmethod
    def get_file_size(self, rel_storage_path: str) -> int:
        """Returns the size of the file in bytes."""
        pass

    @abstractmethod
    def file_exists(self, rel_storage_path: str) -> bool:
        """Checks if the file exists in storage."""
        pass


class LocalStorageProvider(StorageProvider):
    """
    Local filesystem storage provider used for development and local testing.
    Preserves organization isolation under uploads/{org_id}/...
    """

    def __init__(self, base_dir: str = settings.STORAGE_DIR):
        self.base_dir = os.path.abspath(base_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def save_file(self, organization_id: str, upload_file: UploadFile) -> str:
        now = datetime.utcnow()
        year_str = now.strftime("%Y")
        month_str = now.strftime("%B").lower()

        target_dir = os.path.join(self.base_dir, organization_id, "uploads", year_str, month_str)
        os.makedirs(target_dir, exist_ok=True)

        raw_filename = os.path.basename((upload_file.filename or "upload.csv").replace("\\", "/"))
        safe_filename = f"{int(now.timestamp())}_{raw_filename.replace(' ', '_')}"
        full_path = os.path.join(target_dir, safe_filename)

        # Ensure no path traversal outside target_dir
        if not os.path.abspath(full_path).startswith(self.base_dir):
            raise HTTPException(status_code=400, detail="Invalid file destination path.")

        with open(full_path, "wb") as buffer:
            shutil.copyfileobj(upload_file.file, buffer)

        return os.path.relpath(full_path, self.base_dir)

    def get_absolute_path(self, rel_storage_path: str) -> str:
        full_path = os.path.join(self.base_dir, rel_storage_path)
        # Prevent traversal
        resolved = os.path.abspath(full_path)
        if not resolved.startswith(self.base_dir):
            raise ValueError("Path traversal violation detected.")
        return resolved

    def open_stream(self, rel_storage_path: str) -> BinaryIO:
        abs_path = self.get_absolute_path(rel_storage_path)
        return open(abs_path, "rb")

    def delete_file(self, rel_storage_path: str) -> bool:
        try:
            abs_path = self.get_absolute_path(rel_storage_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)
                return True
        except Exception:
            pass
        return False

    def get_file_size(self, rel_storage_path: str) -> int:
        abs_path = self.get_absolute_path(rel_storage_path)
        if os.path.exists(abs_path):
            return os.path.getsize(abs_path)
        return 0

    def file_exists(self, rel_storage_path: str) -> bool:
        try:
            abs_path = self.get_absolute_path(rel_storage_path)
            return os.path.exists(abs_path)
        except Exception:
            return False


class ObjectStorageProvider(StorageProvider):
    """
    S3 / Cloudflare R2 / GCS compatible Object Storage provider for production deployment.
    Does not require immediate cloud credentials during local development.
    """

    def __init__(
        self,
        bucket_name: str = settings.S3_BUCKET_NAME,
        endpoint_url: Optional[str] = settings.S3_ENDPOINT_URL or None,
        access_key: Optional[str] = settings.S3_ACCESS_KEY_ID or None,
        secret_key: Optional[str] = settings.S3_SECRET_ACCESS_KEY or None,
        region_name: str = settings.S3_REGION_NAME or "us-east-1",
        local_cache_dir: str = os.path.join(settings.STORAGE_DIR, "_object_cache")
    ):
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region_name = region_name
        self.local_cache_dir = os.path.abspath(local_cache_dir)
        os.makedirs(self.local_cache_dir, exist_ok=True)
        self._s3_client = None

    def _get_client(self):
        if self._s3_client is not None:
            return self._s3_client
        if not self.bucket_name or not self.access_key or not self.secret_key:
            raise RuntimeError(
                "ObjectStorageProvider configuration missing: S3_BUCKET_NAME, S3_ACCESS_KEY_ID, and S3_SECRET_ACCESS_KEY are required for cloud storage."
            )
        try:
            import boto3
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region_name
            )
            return self._s3_client
        except ImportError:
            raise RuntimeError("boto3 is required for ObjectStorageProvider. Install boto3 to enable cloud storage.")

    def save_file(self, organization_id: str, upload_file: UploadFile) -> str:
        now = datetime.utcnow()
        raw_filename = os.path.basename((upload_file.filename or "upload.csv").replace("\\", "/"))
        safe_filename = f"{int(now.timestamp())}_{raw_filename.replace(' ', '_')}"
        s3_key = f"organizations/{organization_id}/uploads/{now.year}/{now.strftime('%B').lower()}/{safe_filename}"

        client = self._get_client()
        client.upload_fileobj(upload_file.file, self.bucket_name, s3_key)
        return s3_key

    def get_absolute_path(self, rel_storage_path: str) -> str:
        # Download object to local cache if needed for file parsing
        cache_path = os.path.join(self.local_cache_dir, rel_storage_path.replace("/", "_"))
        if not os.path.exists(cache_path):
            client = self._get_client()
            client.download_file(self.bucket_name, rel_storage_path, cache_path)
        return cache_path

    def open_stream(self, rel_storage_path: str) -> BinaryIO:
        client = self._get_client()
        obj = client.get_object(Bucket=self.bucket_name, Key=rel_storage_path)
        return io.BytesIO(obj["Body"].read())

    def delete_file(self, rel_storage_path: str) -> bool:
        try:
            client = self._get_client()
            client.delete_object(Bucket=self.bucket_name, Key=rel_storage_path)
            cache_path = os.path.join(self.local_cache_dir, rel_storage_path.replace("/", "_"))
            if os.path.exists(cache_path):
                os.remove(cache_path)
            return True
        except Exception:
            return False

    def get_file_size(self, rel_storage_path: str) -> int:
        try:
            client = self._get_client()
            head = client.head_object(Bucket=self.bucket_name, Key=rel_storage_path)
            return head.get("ContentLength", 0)
        except Exception:
            return 0

    def file_exists(self, rel_storage_path: str) -> bool:
        try:
            client = self._get_client()
            client.head_object(Bucket=self.bucket_name, Key=rel_storage_path)
            return True
        except Exception:
            return False


def get_storage_provider() -> StorageProvider:
    if settings.STORAGE_PROVIDER in ["s3", "object", "r2", "gcs"]:
        return ObjectStorageProvider()
    return LocalStorageProvider()

storage_service: StorageProvider = get_storage_provider()
