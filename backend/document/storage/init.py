"""Storage Initialization utilities.

Idempotent provisioning of buckets, versioning, and WORM Object Lock policies.
"""

import aioboto3
from botocore.config import Config
import botocore.exceptions

from backend.document.storage.utils import BucketNameBuilder


async def initialize_buckets(region: str = "us-east-1", endpoint_url: str | None = None) -> None:
    """Idempotently initialize all required storage buckets and security policies."""
    doc_bucket = BucketNameBuilder.build_document_bucket()
    audit_bucket = BucketNameBuilder.build_audit_bucket()

    session = aioboto3.Session()
    config = Config(connect_timeout=5, read_timeout=15)

    async with session.client("s3", region_name=region, endpoint_url=endpoint_url, config=config) as client:
        # Initialize Document Bucket (Versioning Only)
        await _ensure_bucket(client, doc_bucket, region, object_lock_enabled_for_bucket=False)
        await _enable_versioning(client, doc_bucket)

        # Initialize Audit Bucket (Versioning + WORM Object Lock)
        await _ensure_bucket(client, audit_bucket, region, object_lock_enabled_for_bucket=True)
        await _enable_versioning(client, audit_bucket)
        await _apply_worm_policy(client, audit_bucket)


async def _ensure_bucket(client, bucket_name: str, region: str, object_lock_enabled_for_bucket: bool) -> None:
    """Create a bucket idempotently, ignoring ownership/exists conflicts."""
    try:
        kwargs = {"Bucket": bucket_name, "ObjectLockEnabledForBucket": object_lock_enabled_for_bucket}
        if region != "us-east-1":
            kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}

        await client.create_bucket(**kwargs)
    except botocore.exceptions.ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code not in ["BucketAlreadyExists", "BucketAlreadyOwnedByYou"]:
            raise e


async def _enable_versioning(client, bucket_name: str) -> None:
    """Enable versioning on the bucket."""
    await client.put_bucket_versioning(
        Bucket=bucket_name,
        VersioningConfiguration={"Status": "Enabled"}
    )


async def _apply_worm_policy(client, bucket_name: str) -> None:
    """Apply Object Lock (WORM) Governance mode for 7 years."""
    await client.put_object_lock_configuration(
        Bucket=bucket_name,
        ObjectLockConfiguration={
            "ObjectLockEnabled": "Enabled",
            "Rule": {
                "DefaultRetention": {
                    "Mode": "GOVERNANCE",
                    "Years": 7
                }
            }
        }
    )
