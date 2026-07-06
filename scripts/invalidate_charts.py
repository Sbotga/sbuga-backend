"""Invalidate all chart views so they re-render on the next asset cycle.

Charts render into the score bundle dir at extraction time (see
asset_handlers/charts.py) and ride the normal per-bundle S3 sync. This removes
the `music/music_score` bundle hashes, deletes the extracted score dirs, and
clears their S3 sync state — so the next server run re-downloads, re-extracts
(which re-renders the charts), and re-uploads them. Nothing is generated here.

    python -m scripts.invalidate_charts            # all regions
    python -m scripts.invalidate_charts en jp      # specific regions
"""

import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg

PATHS = ["music/music_score"]
DEFAULT_REGIONS = ["en", "jp"]


async def main(regions: list[str]) -> None:
    from helpers.config_loader import get_config

    config = get_config()
    pool = await asyncpg.create_pool(
        host=config.psql.host,
        user=config.psql.user,
        database=config.psql.database,
        password=config.psql.password,
        port=config.psql.port,
    )

    for region in regions:
        data_path = Path("pjsk_api") / "data" / region
        hashes_path = data_path / ".bundlehashes.json"

        if hashes_path.exists():
            hashes: dict[str, str] = json.loads(hashes_path.read_text("utf8"))
            removed = [k for k in hashes if any(k.startswith(p + "/") for p in PATHS)]
            for k in removed:
                del hashes[k]
            hashes_path.write_text(json.dumps(hashes, ensure_ascii=False), "utf8")
            print(f"[{region}] removed {len(removed)} entries from bundlehashes")

        assets_path = data_path / "assets"
        tmp_path = data_path / ".bundle_tmp"
        deleted = 0
        for p in PATHS:
            for base in [assets_path, tmp_path]:
                d = base / p
                if d.exists():
                    for child in d.iterdir():
                        if child.is_dir():
                            shutil.rmtree(child)
                            deleted += 1
                        elif child.is_file():
                            child.unlink()
        print(f"[{region}] deleted {deleted} score dirs")

        like = " OR ".join(f"bundle_name LIKE '{p}/%'" for p in PATHS)
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM s3_sync_hashes_v2 WHERE region = $1 AND ({like})",
                region,
            )
            print(f"[{region}] cleared S3 sync state: {result}")

    await pool.close()
    print("done. restart sbuga-backend to re-download, re-render, and re-upload.")


if __name__ == "__main__":
    args = sys.argv[1:]
    asyncio.run(main(args or DEFAULT_REGIONS))
