import asyncio
import hashlib
from typing import Self, override

import boto3  # type: ignore[import-untyped]
from botocore.client import BaseClient  # type: ignore[import-untyped]
from botocore.config import Config  # type: ignore[import-untyped]
from botocore.exceptions import ClientError  # type: ignore[import-untyped]

from atlas_ml_platform.modules.artifacts.application.ports import (
    ArtifactStore,
    StoredArtifact,
)


class S3ArtifactStore(ArtifactStore):
    def __init__(self, client: BaseClient, bucket: str) -> None:
        self._client: BaseClient = client
        self._bucket: str = bucket

    @classmethod
    async def create(
        cls,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        secure: bool = False,
        connect_timeout_seconds: float = 3.0,
        read_timeout_seconds: float = 10.0,
        max_attempts: int = 3,
    ) -> Self:
        scheme = "https" if secure else "http"
        client = boto3.client(
            "s3",
            endpoint_url=f"{scheme}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(
                s3={"addressing_style": "path"},
                connect_timeout=connect_timeout_seconds,
                read_timeout=read_timeout_seconds,
                retries={"max_attempts": max_attempts, "mode": "standard"},
            ),
        )

        store = cls(client, bucket)
        await store._ensure_bucket()
        return store

    async def _ensure_bucket(self) -> None:
        try:
            await asyncio.to_thread(
                self._client.head_bucket,
                Bucket=self._bucket,
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code not in {"404", "NoSuchBucket", "NotFound"}:
                raise
            await asyncio.to_thread(
                self._client.create_bucket,
                Bucket=self._bucket,
            )

    @override
    async def put(
        self,
        *,
        key: str,
        data: bytes,
        content_type: str,
    ) -> StoredArtifact:
        checksum = hashlib.sha256(data).hexdigest()
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

        return StoredArtifact(
            key=key,
            uri=f"s3://{self._bucket}/{key}",
            checksum=checksum,
            size_bytes=len(data),
            content_type=content_type,
        )

    @override
    async def get(self, key: str) -> bytes:
        def _get() -> bytes:
            response = self._client.get_object(
                Bucket=self._bucket,
                Key=key,
            )
            body = response["Body"]
            try:
                return body.read()
            finally:
                body.close()

        return await asyncio.to_thread(_get)

    @override
    async def delete(self, key: str) -> None:
        await asyncio.to_thread(
            self._client.delete_object,
            Bucket=self._bucket,
            Key=key,
        )

    @override
    async def healthcheck(self) -> None:
        await asyncio.to_thread(
            self._client.head_bucket,
            Bucket=self._bucket,
        )

    async def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            await asyncio.to_thread(close)
