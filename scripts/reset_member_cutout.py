"""Wipe every member_cutout / member_cutout_trm bundle so the asset pipeline
redownloads and re-extracts them (now into normal/ + after_training/ subfolders).

Clears three things per region:
  1. the extracted assets under assets/character/member_cutout[_trm]/
  2. those bundles' entries in .bundlehashes.json  -> forces redownload+reextract
  3. their rows in the s3_sync_hashes_v2 table      -> forces re-upload to S3/R2
     (the game bundle hash is unchanged, so without this the new files never sync)

Run from the backend root:  python -m scripts.reset_member_cutout
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
os.chdir(BACKEND_ROOT)
sys.path.insert(0, str(BACKEND_ROOT))

from helpers.config_loader import get_config  # noqa: E402

DATA_ROOT = Path("pjsk_api") / "data"
SUBDIRS = ("character/member_cutout", "character/member_cutout_trm")
PREFIXES = tuple(f"{s}/" for s in SUBDIRS)


def reset_filesystem() -> None:
    if not DATA_ROOT.exists():
        print(f"no data dir at {DATA_ROOT.resolve()}")
        return

    for region_dir in sorted(p for p in DATA_ROOT.iterdir() if p.is_dir()):
        region = region_dir.name

        for sub in SUBDIRS:
            extracted = region_dir / "assets" / sub
            if extracted.exists():
                shutil.rmtree(extracted, ignore_errors=True)
                print(f"[{region}] removed extracted {sub}")
            tmp = region_dir / ".bundle_tmp" / sub
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)
                print(f"[{region}] removed tmp download {sub}")

        hashes_path = region_dir / ".bundlehashes.json"
        if hashes_path.exists():
            try:
                hashes = json.loads(hashes_path.read_text("utf8"))
            except (json.JSONDecodeError, OSError):
                hashes = {}
            removed = [k for k in hashes if k.startswith(PREFIXES)]
            for k in removed:
                del hashes[k]
            if removed:
                hashes_path.write_text(json.dumps(hashes, indent=4), "utf8")
            print(f"[{region}] dropped {len(removed)} .bundlehashes.json entries")


async def reset_db() -> None:
    import asyncpg

    cfg = get_config().psql
    try:
        conn = await asyncpg.connect(
            host=cfg.host,
            user=cfg.user,
            database=cfg.database,
            password=cfg.password,
            port=cfg.port,
            ssl="disable",
        )
    except Exception as e:
        print(f"\nDB: could not connect ({e}); skipped s3_sync_hashes_v2 cleanup.")
        print("    re-uploads to S3/R2 won't trigger until those rows are cleared.")
        return
    try:
        result = await conn.execute(
            "DELETE FROM s3_sync_hashes_v2 "
            "WHERE bundle_name LIKE 'character/member_cutout/%' "
            "OR bundle_name LIKE 'character/member_cutout_trm/%'"
        )
        print(f"\nDB: cleared s3_sync_hashes_v2 rows -> {result}")
    except asyncpg.UndefinedTableError:
        print("\nDB: s3_sync_hashes_v2 doesn't exist yet; nothing to clear.")
    finally:
        await conn.close()


def main() -> None:
    reset_filesystem()
    asyncio.run(reset_db())
    print(
        "\nDone. On the next asset cycle these bundles redownload, re-extract into "
        "normal/ + after_training/ subfolders, and re-upload."
    )


if __name__ == "__main__":
    main()
