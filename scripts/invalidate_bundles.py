import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg

PATHS = [
    "music/long",
    "music/short",
]

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
        deleted_dirs = 0
        deleted_tmp = 0
        for p in PATHS:
            for base in [assets_path, tmp_path]:
                d = base / p
                if d.exists():
                    for child in d.iterdir():
                        if child.is_dir():
                            shutil.rmtree(child)
                            deleted_dirs += 1
                        elif child.is_file():
                            child.unlink()
                            deleted_tmp += 1
        print(f"[{region}] deleted {deleted_dirs} dirs, {deleted_tmp} tmp files")

        like_clauses = " OR ".join(f"bundle_name LIKE '{p}/%'" for p in PATHS)
        async with pool.acquire() as conn:
            result = await conn.execute(
                f"DELETE FROM s3_sync_hashes_v2 WHERE region = $1 AND ({like_clauses})",
                region,
            )
            print(f"[{region}] db: {result}")

    await pool.close()
    print("done. restart sbuga-backend to re-process.")


asyncio.run(main())
