"""S3-compatible object storage for evidence packages (AWS S3, MinIO, R2)."""

from __future__ import annotations

import hashlib

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.core.exceptions import StorageError
from app.core.logging import get_logger

logger = get_logger(__name__)


class ObjectStorage:
    def __init__(self) -> None:
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            use_ssl=settings.S3_USE_SSL,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )
        self.bucket = settings.S3_BUCKET

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError:
            try:
                self._client.create_bucket(Bucket=self.bucket)
                logger.info("bucket_created", bucket=self.bucket)
            except (ClientError, BotoCoreError) as exc:
                raise StorageError(f"Could not create bucket '{self.bucket}': {exc}") from exc

    def put_bytes(self, key: str, data: bytes, content_type: str) -> str:
        self.ensure_bucket()
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata={"sha256": hashlib.sha256(data).hexdigest()},
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Upload of '{key}' failed: {exc}") from exc
        logger.info("object_uploaded", key=key, bytes=len(data))
        return key

    def presigned_url(self, key: str, expires: int | None = None) -> str:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires or settings.S3_PRESIGN_EXPIRY_SECONDS,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(f"Could not presign '{key}': {exc}") from exc

    def healthy(self) -> bool:
        try:
            self._client.list_buckets()
            return True
        except (ClientError, BotoCoreError):
            return False


def get_storage() -> ObjectStorage:
    return ObjectStorage()
