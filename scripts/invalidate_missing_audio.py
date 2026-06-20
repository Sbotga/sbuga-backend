import asyncio
import json
import shutil
import sys
import os
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import asyncpg

REGIONS = ["en", "jp"]


async def main():
    from helpers.config_loader import get_config

    config = get_config()

    pool = await asyncpg.create_pool(
        host=config.psql.host,
        user=config.psql.user,
        database=config.psql.database,
        password=config.psql.password,
        port=config.psql.port,
    )

    for region in REGIONS:
        data_path = Path("pjsk_api") / "data" / region
        assets_path = data_path / "assets"
        hashes_path = data_path / ".bundlehashes.json"

        if not hashes_path.exists():
            print(f"[{region}] no bundlehashes file, skipping")
            continue

        hashes: dict[str, str] = json.loads(hashes_path.read_text("utf8"))

        missing_bundles: list[str] = []
        for bundle_name in list(hashes.keys()):
            if not bundle_name.startswith("music/long/") and not bundle_name.startswith(
                "music/short/"
            ):
                continue
            bundle_dir = assets_path / bundle_name
            if not bundle_dir.exists():
                missing_bundles.append(bundle_name)
                continue
            mp3s = list(bundle_dir.glob("*.mp3"))
            has_silence_removed = any("_silence_removed" in f.name for f in mp3s)
            if not mp3s or not has_silence_removed:
                missing_bundles.append(bundle_name)

        if not missing_bundles:
            print(f"[{region}] all audio bundles have mp3s")
            continue

        print(f"[{region}] {len(missing_bundles)} bundles missing mp3s:")
        for b in missing_bundles:
            print(f"  - {b}")

        tmp_path = data_path / ".bundle_tmp"
        for b in missing_bundles:
            if b in hashes:
                del hashes[b]
            bundle_dir = assets_path / b
            if bundle_dir.exists():
                shutil.rmtree(bundle_dir)
            tmp_file = tmp_path / b
            if tmp_file.exists():
                tmp_file.unlink()
        hashes_path.write_text(json.dumps(hashes, ensure_ascii=False), "utf8")

        like_clauses = " OR ".join(f"bundle_name = '{b}'" for b in missing_bundles)
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM s3_sync_hashes_v2 WHERE region = $1 AND ({like_clauses})",
                region,
            )
            print(f"[{region}] db: {result}")

    await pool.close()
    print("done. restart sbuga-backend to re-process missing audio.")


asyncio.run(main())
