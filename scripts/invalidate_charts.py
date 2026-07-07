"""Invalidate chart views everywhere for a full re-render.

Deletes rendered chart files locally, deletes them from R2, and clears the
`s3_sync_hashes_v2` rows for score bundles so the next sync re-uploads each
bundle with its freshly rendered charts. Also drops the legacy `chart_hashes`
table. On the next asset cycle the server re-renders and re-syncs everything.

Run from the repo root (needs config.yml):

    python -m scripts.invalidate_charts            # all regions
    python -m scripts.invalidate_charts en jp      # specific regions
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aioboto3
import asyncpg

from helpers.config_loader import get_config

DEFAULT_REGIONS = ["en", "jp"]
CHART_EXTS = (".png", ".webp", ".svg")


def _delete_local(region: str) -> int:
    score_root = Path("pjsk_api") / "data" / region / "assets" / "music" / "music_score"
    if not score_root.exists():
        return 0
    deleted = 0
    for f in score_root.glob("*/*"):
        if f.suffix in CHART_EXTS:
            f.unlink()
            deleted += 1
    return deleted


async def _delete_r2(bucket, region: str) -> int:
    prefix = f"pjsk_data/{region}/music/music_score/"
    deleted = 0
    batch: list[dict[str, str]] = []
    async for obj in bucket.objects.filter(Prefix=prefix):
        if not obj.key.endswith(CHART_EXTS):
            continue
        batch.append({"Key": obj.key})
        if len(batch) == 1000:
            await bucket.delete_objects(Delete={"Objects": batch})
            deleted += len(batch)
            batch = []
    if batch:
        await bucket.delete_objects(Delete={"Objects": batch})
        deleted += len(batch)
    return deleted


async def main(regions: list[str]) -> None:
    config = get_config()

    db = await asyncpg.create_pool(
        host=config.psql.host,
        user=config.psql.user,
        database=config.psql.database,
        password=config.psql.password,
        port=config.psql.port,
        min_size=1,
        max_size=2,
        ssl="disable",
    )

    session = aioboto3.Session(
        aws_access_key_id=config.s3.access_key_id,
        aws_secret_access_key=config.s3.secret_access_key,
        region_name=config.s3.location,
    )

    async with session.resource("s3", endpoint_url=config.s3.endpoint) as s3:
        bucket = await s3.Bucket(config.s3.bucket_name)
        for region in regions:
            local = _delete_local(region)
            print(f"[{region}] deleted {local} local chart files")

            remote = await _delete_r2(bucket, region)
            print(f"[{region}] deleted {remote} chart files from R2")

            try:
                async with db.acquire() as conn:
                    result = await conn.execute(
                        "DELETE FROM s3_sync_hashes_v2 "
                        "WHERE region = $1 AND bundle_name LIKE 'music/music_score/%'",
                        region,
                    )
                print(f"[{region}] cleared sync rows ({result})")
            except asyncpg.exceptions.UndefinedTableError:
                print(f"[{region}] no sync table yet, nothing to clear")

    async with db.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS chart_hashes")

    await db.close()
    print("done. restart sbuga-backend to re-render and re-upload all charts.")


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main(args or DEFAULT_REGIONS))
