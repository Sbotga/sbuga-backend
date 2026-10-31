import json
import aiofiles
import asyncpg

from fastapi import APIRouter, Request, HTTPException, status
from typing import Literal

from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, COMMON_RESPONSES

router = APIRouter()


@router.get(
    "",
    summary="Get asset bundle hashes",
    description=(
        "Returns bundle hashes for music_score bundles, used by SSS to detect chart changes. "
        "With synced=true, only bundles already uploaded to S3 are returned, with the hash that was uploaded."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "bundles": {
                            "music/music_score/0001_01": {
                                "hash": "abc123",
                                "fileSize": 12345,
                            }
                        }
                    }
                }
            },
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def get_assetinfo(
    request: Request,
    region: Literal["en", "jp"] = "jp",
    filter: str = "music/music_score",
    synced: bool = False,
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    assetinfo_path = client.data_path / "assetinfo_android.json"
    if not assetinfo_path.exists():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="assetinfo not available",
        )

    async with aiofiles.open(assetinfo_path, "r", encoding="utf8") as f:
        assetinfo = json.loads(await f.read())

    # surface locally-bundled removed_data bundles (e.g. delisted song charts) the
    # same way as live ones
    from pjsk_api.asset_handlers.removed_data import inject_assetinfo_bundles

    inject_assetinfo_bundles(assetinfo, region)

    bundles = assetinfo.get("bundles", {})

    if filter:
        bundles = {
            k: {"hash": v.get("hash", ""), "fileSize": v.get("fileSize", 0)}
            for k, v in bundles.items()
            if k.startswith(filter)
        }

    if synced:
        uploaded = await _get_synced_hashes(app, region, list(bundles))
        if uploaded is not None:
            bundles = {
                k: {**v, "hash": uploaded[k]}
                for k, v in bundles.items()
                if k in uploaded
            }

    return {"bundles": bundles}


async def _get_synced_hashes(
    app: SbugaFastAPI, region: str, bundle_names: list[str]
) -> dict[str, str] | None:
    try:
        async with app.db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT bundle_name, bundle_hash FROM s3_sync_hashes_v2 "
                "WHERE region = $1 AND bundle_name = ANY($2::text[])",
                region,
                bundle_names,
            )
    except asyncpg.UndefinedTableError:
        return None
    return {row["bundle_name"]: row["bundle_hash"] for row in rows}
