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
        jacket_dir = assets_path / "music" / "jacket"
        if not jacket_dir.exists():
            print(f"[{region}] no jacket dir, skipping")
            continue

        missing_bundles: list[str] = []
        for bundle_dir in jacket_dir.iterdir():
            if not bundle_dir.is_dir():
                continue
            name = bundle_dir.name
            bundle_name = f"music/jacket/{name}"

            has_jacket = (bundle_dir / f"{name}.png").exists()
            if not has_jacket:
                continue

            has_v1 = (bundle_dir / f"{name}_v1.png").exists()
            has_v3 = (bundle_dir / f"{name}_v3.png").exists()

            if not has_v1 or not has_v3:
                missing_bundles.append(bundle_name)

        if not missing_bundles:
            print(f"[{region}] all jacket bundles have backgrounds")
            continue

        print(f"[{region}] {len(missing_bundles)} jacket bundles missing backgrounds:")
        for b in missing_bundles:
            print(f"  - {b}")

        for b in missing_bundles:
            if b in hashes:
                del hashes[b]
            bundle_path = assets_path / b
            if bundle_path.exists():
                shutil.rmtree(bundle_path)
        hashes_path.write_text(json.dumps(hashes, ensure_ascii=False), "utf8")

        like_clauses = " OR ".join(f"bundle_name = '{b}'" for b in missing_bundles)
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM s3_sync_hashes_v2 WHERE region = $1 AND ({like_clauses})",
                region,
            )
            print(f"[{region}] db: {result}")

    await pool.close()
    print("done. restart sbuga-backend to re-process missing backgrounds.")


asyncio.run(main())
