import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from pathlib import Path
import logging
from typing import Any, Optional
import asyncio

logger = logging.getLogger(__name__)

class S3Client:
    def __init__(self, bucket: str, endpoint: str, access_key: str, secret_key: str):
        self.bucket = bucket
        self.client = boto3.client('s3', endpoint_url=endpoint,
                                   aws_access_key_id=access_key,
                                   aws_secret_access_key=secret_key,
                                   config=Config(signature_version='s3v4'))

    def generate_presigned_url(self, object_key: str, content_type: str) -> str:
        return self.client.generate_presigned_url(
            ClientMethod='put_object',
            Params={'Bucket': self.bucket, 'Key': object_key, 'ContentType': content_type},
            ExpiresIn=900
        )

    async def upload_file(self, local_path: str, object_key: str) -> None:
        try:
            await asyncio.to_thread(
                self.client.upload_file,
                Filename=local_path,
                Bucket=self.bucket,
                Key=object_key
            )
            logger.info(f"Uploaded {local_path} -> s3://{self.bucket}/{object_key}")
        except ClientError as e:
            logger.error(f"Failed to upload {local_path} to {object_key}: {e}")
            raise

    async def download_file(self, object_key: str, local_path: str) -> None:
        try:
            path_obj = Path(local_path).resolve()
            path_obj.parent.mkdir(parents=True, exist_ok=True)
            local_path_str = str(path_obj)
            await asyncio.to_thread(
                self.client.download_file,
                Bucket=self.bucket,
                Key=object_key,
                Filename=local_path_str
            )
            logger.info(f"Downloaded s3://{self.bucket}/{object_key} -> {local_path}")
        except ClientError as e:
            logger.error(f"Failed to download {object_key} to {local_path}: {e}")
            raise

    def list_files(self, prefix: str) -> list[str]:
        try:
            response = self.client.list_objects_v2(Bucket=self.bucket, Prefix=prefix)
            if 'Contents' not in response:
                return []
            return [obj['Key'] for obj in response['Contents'] if not obj['Key'].endswith('/')]
        except ClientError as e:
            logger.error(f"Failed to list objects in {prefix}: {e}")
            raise

    async def read_text(self, object_key: str, encoding: str = 'utf-8') -> Optional[str]:
        def _read():
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
            body = response['Body'].read()
            return body.decode(encoding)
        try:
            return await asyncio.to_thread(_read())
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                logger.warning(f"Object not found: s3://{self.bucket}/{object_key}")
                return None
            logger.error(f"Failed to read text from {object_key}: {e}")
            raise

    async def read_json(self, object_key: str) -> dict | None:
        def _read():
            import json
            response = self.client.get_object(Bucket=self.bucket, Key=object_key)
            content = response['Body'].read().decode('utf-8')
            return json.loads(content)
        try:
            return await asyncio.to_thread(_read)
        except ClientError as e:
            logger.warning(f"Could not read JSON at {object_key}: {e}")
            return None

    async def delete_folder(self, prefix: str):
        try:
            def _delete_sync():
                paginator = self.client.get_paginator('list_objects_v2')
                pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
                delete_us = []
                for page in pages:
                    if 'Contents' in page:
                        for obj in page['Contents']:
                            delete_us.append({'Key': obj['Key']})
                            if len(delete_us) >= 1000:
                                self.client.delete_objects(Bucket=self.bucket, Delete={'Objects': delete_us})
                                delete_us = []
                if delete_us:
                    self.client.delete_objects(Bucket=self.bucket, Delete={'Objects': delete_us})
            await asyncio.to_thread(_delete_sync)
            logger.info(f"Deleted S3 folder: {prefix}")
        except ClientError as e:
            logger.error(f"Failed to delete folder {prefix}: {e}")
