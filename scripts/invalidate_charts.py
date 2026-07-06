"""Invalidate and regenerate all chart views.

Charts render into the score bundle dir
(`assets/music/music_score/{padded}_01/{difficulty}.png`) and ride the normal
per-bundle S3 sync. This deletes every rendered chart PNG, re-renders them from
the already-extracted `.txt` scores (no re-download), and clears the S3 sync
state for those bundles so the next server sync re-uploads them to R2.

    python -m scripts.invalidate_charts            # all regions
    python -m scripts.invalidate_charts en jp      # specific regions
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg

from pjsk_api.asset_handlers.charts import generate_views

DEFAULT_REGIONS = ["en", "jp", "tw", "kr"]


async def main(regions: list[str]) -> None:
    from helpers.config_loader import get_config

    config = get_config()
    s3_base = getattr(config.s3, "base_url", None)

    pool = await asyncpg.create_pool(
        host=config.psql.host,
        user=config.psql.user,
        database=config.psql.database,
        password=config.psql.password,
        port=config.psql.port,
    )

    for region in regions:
        data_path = Path("pjsk_api") / "data" / region
        score_root = data_path / "assets" / "music" / "music_score"
        master_path = data_path / "master" / "musics.json"

        if not master_path.exists() or not score_root.exists():
            print(f"[{region}] no scores/masterdata, skipping")
            continue

        deleted = 0
        for ext in ("png", "webp", "svg"):
            for f in score_root.glob(f"*/*.{ext}"):
                f.unlink()
                deleted += 1
        print(f"[{region}] deleted {deleted} chart files")

        musics = json.loads(master_path.read_text(encoding="utf8"))
        count = await generate_views(
            data_path, region, s3_base, musics, padded_ids=None, force=True
        )
        print(f"[{region}] regenerated {count} chart views")

        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM s3_sync_hashes_v2 WHERE region = $1 "
                "AND bundle_name LIKE 'music/music_score/%'",
                region,
            )
        print(f"[{region}] cleared S3 sync state: {result}")

    await pool.close()
    print("done. restart sbuga-backend (or wait for next asset cycle) to re-upload.")


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main(args or DEFAULT_REGIONS))
