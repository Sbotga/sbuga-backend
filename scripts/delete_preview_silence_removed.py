import asyncio
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg
import aioboto3

REGIONS = ["en", "jp"]


async def main():
    from helpers.config_loader import get_config

    config = get_config()

    # delete local files
    for region in REGIONS:
        short_dir = Path("pjsk_api") / "data" / region / "assets" / "music" / "short"
        if not short_dir.exists():
            continue
        deleted = 0
        for bundle_dir in short_dir.iterdir():
            if not bundle_dir.is_dir():
                continue
            for f in bundle_dir.glob("*_silence_removed.mp3"):
                f.unlink()
                deleted += 1
        print(f"[{region}] deleted {deleted} local preview silence_removed files")

    # delete from S3
    s3_config = config.s3
    session = aioboto3.Session(
        aws_access_key_id=s3_config.access_key_id,
        aws_secret_access_key=s3_config.secret_access_key,
        region_name=s3_config.location,
    )
    async with session.resource("s3", endpoint_url=s3_config.endpoint) as s3:
        bucket = await s3.Bucket(s3_config.bucket_name)
        for region in REGIONS:
            prefix = f"pjsk_data/{region}/music/short/"
            deleted = 0
            batch: list[dict[str, str]] = []
            async for obj in bucket.objects.filter(Prefix=prefix):
                if "_silence_removed" in obj.key:
                    batch.append({"Key": obj.key})
                    if len(batch) == 1000:
                        await bucket.delete_objects(Delete={"Objects": batch})
                        deleted += len(batch)
                        batch = []
            if batch:
                await bucket.delete_objects(Delete={"Objects": batch})
                deleted += len(batch)
            print(f"[{region}] deleted {deleted} S3 preview silence_removed files")

    # invalidate S3 sync hashes for short bundles so they re-upload without the bad files
    pool = await asyncpg.create_pool(
        host=config.psql.host,
        user=config.psql.user,
        database=config.psql.database,
        password=config.psql.password,
        port=config.psql.port,
    )
    async with pool.acquire() as conn:
        result = await conn.execute(
            "DELETE FROM s3_sync_hashes_v2 WHERE bundle_name LIKE 'music/short/%'"
        )
        print(f"db: {result}")
    await pool.close()

    print(
        "done. restart sbuga-backend to re-sync short bundles (without silence_removed)."
    )


asyncio.run(main())
