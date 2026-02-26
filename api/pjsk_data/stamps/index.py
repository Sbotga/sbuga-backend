from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, COMMON_RESPONSES
from typing import Literal

router = APIRouter()


@router.get(
    "",
    summary="Get stamps",
    description=(
        "Returns a list of all stamps from the PJSK master data for a given region. "
        "`image_url` points to the stamp image and `balloon_url` points to the balloon overlay. "
        "`image_type` defaults to `webp`. "
        "`published_at` is in milliseconds since Unix epoch."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "stamps": [
                            {
                                "stamp_type": "illustration",
                                "name": "[スタンプ]ミク：よろしく",
                                "character_ids": [21],
                                "game_character_unit_id": 21,
                                "published_at": 1233284400000,
                                "description": "ゲーム開始時に獲得",
                                "image_url": "https://sbuga.com/api/pjsk_data/assets/stamp/stamp0001/stamp0001.webp?region=en",
                                "balloon_url": "https://sbuga.com/api/pjsk_data/assets/stamp_balloon/balloon_stamp_01/balloon_stamp_01.webp?region=en",
                            }
                        ]
                    }
                }
            },
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def get_stamps(
    request: Request,
    region: Literal["en", "jp"],
    image_type: Literal["png", "webp"] = "webp",
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    stamps_data: list = await client.get_master("stamps")

    def get_character_ids(stamp: dict) -> list[int]:
        ids = []
        i = 1
        while f"characterId{i}" in stamp:
            ids.append(stamp[f"characterId{i}"])
            i += 1
        return ids

    def make_asset_url(path: str) -> str:
        return f"{app.base_url}/api/pjsk_data/assets/{path}?region={region}"

    stamps = [
        {
            "stamp_type": stamp["stampType"],
            "name": stamp["name"],
            "character_ids": get_character_ids(stamp),
            "game_character_unit_id": stamp.get("gameCharacterUnitId"),
            "published_at": stamp.get("archivePublishedAt"),
            "description": stamp.get("description"),
            "image_url": make_asset_url(
                f"stamp/{stamp['assetbundleName']}/{stamp['assetbundleName']}.{image_type}"
            ),
            "balloon_url": make_asset_url(
                f"stamp_balloon/{stamp['balloonAssetbundleName']}/{stamp['balloonAssetbundleName']}.{image_type}"
            ),
        }
        for stamp in stamps_data
    ]

    return {"stamps": stamps}
