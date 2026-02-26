from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from typing import Literal

router = APIRouter()


def _is_comic(tip: dict) -> bool:
    return "assetbundleName" in tip and "description" not in tip


@router.get(
    "",
    summary="Get comics",
    description=(
        "Returns a list of all comics from the PJSK master data for a given region. "
        "`image_type` defaults to `webp`. "
        "`from_user_rank` and `to_user_rank` indicate the player rank range required to unlock the comic."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "comics": [
                            {
                                "title": "Comic Title",
                                "image_url": "https://sbuga.com/api/pjsk_data/assets/comic/one_frame/comic_001.webp?region=en",
                                "from_user_rank": 1,
                                "to_user_rank": 10,
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
async def get_comics(
    request: Request,
    region: Literal["en", "jp"],
    image_type: Literal["png", "webp"] = "webp",
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.InternalServerError.value,
        )

    tips: list = await client.get_master("tips")

    comics = [
        {
            "title": tip["title"],
            "image_url": app.base_url
            + f"/api/pjsk_data/assets/comic/one_frame/{tip['assetbundleName']}.{image_type}?region={region}",
            "from_user_rank": tip["fromUserRank"],
            "to_user_rank": tip["toUserRank"],
        }
        for tip in tips
        if _is_comic(tip)
    ]

    return {"comics": comics}
