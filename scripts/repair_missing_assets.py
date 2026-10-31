"""Requeue bundles the backend marked as done whose files never made it.

A bundle is re-downloaded when its local output is missing or incomplete, and
only re-uploaded when the local files are fine but missing on S3.

Run from the repo root (needs config.yml), ideally with sbuga-backend stopped:

    python -m scripts.repair_missing_assets                   # en + jp, music/ bundles
    python -m scripts.repair_missing_assets jp --dry-run      # only report
    python -m scripts.repair_missing_assets jp --prefix event_story/
    python -m scripts.repair_missing_assets jp --bundle music/music_score/0793_01
"""

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aioboto3
import asyncpg

from helpers.config_loader import get_config

DEFAULT_REGIONS = ["en", "jp"]
S3_DATA_PREFIX = "pjsk_data/"
CHART_FILES = {
    f"{d}.txt" for d in ("easy", "normal", "hard", "expert", "master", "append")
}


def _local_files(bundle_dir: Path) -> list[Path]:
    if not bundle_dir.is_dir():
        return []
    return [f for f in bundle_dir.rglob("*") if f.is_file()]


def _filler_vocals(data_path: Path) -> set[str]:
    # vocal bundles whose long audio gets a _silence_removed.mp3 (see process.py)
    master = data_path / "master"
    try:
        musics = json.loads((master / "musics.json").read_text("utf8"))
        vocals = json.loads((master / "musicVocals.json").read_text("utf8"))
    except FileNotFoundError:
        return set()
    has_filler = {m["id"] for m in musics if m.get("fillerSec", 0) > 0}
    return {v["assetbundleName"] for v in vocals if v.get("musicId") in has_filler}


def _local_problem(
    bundle_name: str, files: list[Path], filler_vocals: set[str]
) -> str | None:
    if not files:
        return "no local files"
    names = {f.name for f in files}
    if bundle_name.startswith("music/music_score/") and not names & CHART_FILES:
        return "no charts"
    if bundle_name.startswith(("music/long/", "music/short/")) and not any(
        n.endswith(".mp3") for n in names
    ):
        return "no mp3"
    if (
        bundle_name.startswith("music/long/")
        and bundle_name.rsplit("/", 1)[1] in filler_vocals
        and not any(n.endswith("_silence_removed.mp3") for n in names)
    ):
        return "no _silence_removed.mp3"
    if bundle_name.startswith("music/jacket/") and not (
        any(n.endswith("_v1.png") for n in names)
        and any(n.endswith("_v3.png") for n in names)
    ):
        return "no backgrounds"
    return None


async def _list_keys(bucket, prefix: str) -> set[str]:
    keys: set[str] = set()
    async for obj in bucket.objects.filter(Prefix=prefix):
        keys.add(obj.key)
    return keys


async def _repair_region(
    region: str,
    prefix: str,
    forced: list[str],
    dry_run: bool,
    db: asyncpg.Pool,
    bucket,
) -> None:
    data_path = Path("pjsk_api") / "data" / region
    assets_path = data_path / "assets"
    hashes_path = data_path / ".bundlehashes.json"
    if not hashes_path.exists():
        print(f"[{region}] no bundlehashes file, skipping")
        return
    hashes: dict[str, str] = json.loads(hashes_path.read_text("utf8"))

    try:
        async with db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT bundle_name FROM s3_sync_hashes_v2 WHERE region = $1", region
            )
        synced = {row["bundle_name"] for row in rows}
    except asyncpg.exceptions.UndefinedTableError:
        synced = set()

    remote = await _list_keys(bucket, f"{S3_DATA_PREFIX}{region}/{prefix}")
    print(f"[{region}] {len(remote)} objects on S3 under {prefix or '/'}")

    filler_vocals = _filler_vocals(data_path)
    redownload: dict[str, str] = {name: "forced" for name in forced}
    reupload: dict[str, str] = {}
    for name in hashes:
        if not name.startswith(prefix) or name in redownload:
            continue
        files = _local_files(assets_path / name)
        problem = _local_problem(name, files, filler_vocals)
        if problem:
            redownload[name] = problem
            continue
        if name not in synced:
            continue  # the normal sync already picks these up
        missing = sum(
            1
            for f in files
            if f"{S3_DATA_PREFIX}{region}/{f.relative_to(assets_path).as_posix()}"
            not in remote
        )
        if missing:
            reupload[name] = f"{missing}/{len(files)} files missing on S3"

    for name, why in sorted(redownload.items()):
        print(f"[{region}] re-download {name}: {why}")
    for name, why in sorted(reupload.items()):
        print(f"[{region}] re-upload {name}: {why}")
    print(f"[{region}] {len(redownload)} to re-download, {len(reupload)} to re-upload")

    if dry_run or not (redownload or reupload):
        return

    tmp_path = data_path / ".bundle_tmp"
    for name in redownload:
        hashes.pop(name, None)
        bundle_dir = assets_path / name
        if bundle_dir.exists():
            shutil.rmtree(bundle_dir)
        tmp_file = tmp_path / name
        if tmp_file.exists():
            tmp_file.unlink()
    hashes_path.write_text(json.dumps(hashes, indent=4), "utf8")

    try:
        async with db.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM s3_sync_hashes_v2 "
                "WHERE region = $1 AND bundle_name = ANY($2::text[])",
                region,
                [*redownload, *reupload],
            )
        print(f"[{region}] cleared sync rows ({result})")
    except asyncpg.exceptions.UndefinedTableError:
        pass


async def main(args: argparse.Namespace) -> None:
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
        for region in args.regions or DEFAULT_REGIONS:
            await _repair_region(
                region, args.prefix, args.bundle, args.dry_run, db, bucket
            )

    await db.close()
    if args.dry_run:
        print("dry run, nothing changed.")
    else:
        print("done. restart sbuga-backend to re-process.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("regions", nargs="*")
    parser.add_argument("--prefix", default="music/")
    parser.add_argument("--bundle", action="append", default=[])
    parser.add_argument("--dry-run", action="store_true")
    asyncio.run(main(parser.parse_args()))
