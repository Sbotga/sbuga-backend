from fastapi import APIRouter, Request, HTTPException, status
from typing import Literal

from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, COMMON_RESPONSES, ERROR_RESPONSE

router = APIRouter()

ALLOWED_FILES = {
    "events",
    "eventDeckBonuses",
    "worldBlooms",
    "gameCharacters",
    "gameCharacterUnits",
    "characterProfiles",
    "cheerfulCarnivalTeams",
    "cards",
    "gachas",
    "eventStories",
    "eventStoryUnits",
    "musics",
    "musicVocals",
    "musicDifficulties",
    "outsideCharacters",
    "unitProfiles",
    "skills",
}


@router.get(
    "/{file}",
    summary="Get a raw masterdata file",
    description=(
        "Returns the raw, unmodified masterdata JSON for the given file "
        "(filename without `.json`, exact game naming). Allowed files: "
        + ", ".join(f"`{f}`" for f in sorted(ALLOWED_FILES))
    ),
    responses={
        200: {
            "description": "Success (raw masterdata contents, usually a JSON array)",
            "content": {"application/json": {"example": [{"id": 1}]}},
        },
        404: {
            "description": f"File not allowed or not present for this region. (`{ErrorDetailCode.NotFound}`)",
            **ERROR_RESPONSE,
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def get_master_file(
    request: Request,
    file: str,
    region: Literal["en", "jp", "tw", "kr"],
):
    app: SbugaFastAPI = request.app

    if file not in ALLOWED_FILES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    try:
        return await client.get_master(file)
    except OSError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )
