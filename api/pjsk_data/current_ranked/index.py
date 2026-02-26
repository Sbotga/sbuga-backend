from core import SbugaFastAPI
from fastapi import APIRouter, Request, HTTPException, status
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from pjsk_api.requests import ranked as pjsk_ranked_requests
from typing import Literal
import time
import asyncio

router = APIRouter()

cached = {}
locks: dict[str, asyncio.Lock] = {}
CACHE_TTL = 300


def get_lock(region: str) -> asyncio.Lock:
    if region not in locks:
        locks[region] = asyncio.Lock()
    return locks[region]


def get_current_season(seasons: list) -> dict | None:
    now = int(time.time() * 1000)

    for season in seasons:
        if season["startAt"] < now < season["closedAt"]:
            return {"id": season["id"], "status": "going"}

    if not seasons:
        return None

    if len(seasons) == 1 and now < seasons[0]["startAt"]:
        return None

    latest = seasons[-1]
    return {"id": latest["id"], "status": "end"}


@router.get(
    "",
    summary="Current ranked season",
    description=(
        "Returns the current PJSK ranked season data including the top 100 leaderboard. "
        "`season_status` is one of `going` or `end`. "
        "Data is cached for **5 minutes** - `next_available_update` indicates when fresh data will be available. "
        "If there is no active season, `season_id` will be `null` and no leaderboard data is returned."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "examples": {
                        "active": {
                            "summary": "Active season",
                            "value": {
                                "updated": 1700000000.0,
                                "next_available_update": 1700000300.0,
                                "season_id": 123,
                                "season_status": "going",
                                "top_100": {},
                            },
                        },
                        "none": {
                            "summary": "No active season",
                            "value": {
                                "updated": 1700000000.0,
                                "next_available_update": 1700000300.0,
                                "season_id": None,
                            },
                        },
                    }
                }
            },
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def current_ranked(request: Request, region: Literal["en", "jp"]):
    app: SbugaFastAPI = request.app

    prev = cached.get(region, {})
    if prev.get("updated", 0) + CACHE_TTL > time.time():
        return prev

    lock = get_lock(region)

    async with lock:
        prev = cached.get(region, {})
        if prev.get("updated", 0) + CACHE_TTL > time.time():
            return prev

        client = app.pjsk_clients.get(region)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=ErrorDetailCode.InternalServerError.value,
            )

        seasons = await client.get_master("rankMatchSeasons")
        season = get_current_season(seasons)

        updated = time.time()

        if not season:
            return {
                "updated": updated,
                "next_available_update": updated + CACHE_TTL,
                "season_id": None,
            }

        top_100 = await app.pjsk_request(
            region, pjsk_ranked_requests.leaderboard_request(client, season["id"])
        )

        data = {
            "updated": updated,
            "next_available_update": updated + CACHE_TTL,
            "season_id": season["id"],
            "season_status": season["status"],
            "top_100": top_100,
        }
        cached[region] = data

        return data
