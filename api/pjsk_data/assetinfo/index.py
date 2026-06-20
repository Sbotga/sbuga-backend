import json
import aiofiles

from fastapi import APIRouter, Request, HTTPException, status
from typing import Literal

from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, COMMON_RESPONSES

router = APIRouter()


@router.get(
    "",
    summary="Get asset bundle hashes",
    description="Returns bundle hashes for music_score bundles, used by SSS to detect chart changes.",
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

    bundles = assetinfo.get("bundles", {})

    if filter:
        bundles = {
            k: {"hash": v.get("hash", ""), "fileSize": v.get("fileSize", 0)}
            for k, v in bundles.items()
            if k.startswith(filter)
        }

    return {"bundles": bundles}
