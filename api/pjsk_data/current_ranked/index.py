from core import SbugaFastAPI
from fastapi import APIRouter, Request, HTTPException, status
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from pjsk_api.requests import ranked as pjsk_ranked_requests
from typing import Literal
import time
import asyncio
import json
import aiofiles
import aiofiles.os
from pathlib import Path

router = APIRouter()

cached: dict[str, dict] = {}
locks: dict[str, asyncio.Lock] = {}
_file_cache_loaded: set[str] = set()
CACHE_TTL = 300
CACHE_FILE = "ranked.json"


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


async def _try_load_file_cache(region: str, cache_path: Path) -> None:
    """Attempt to load file cache into memory. Only called once per region."""
    try:
        async with aiofiles.open(cache_path, "r", encoding="utf8") as f:
            data = json.loads(await f.read())
        cached[region] = data
    except Exception:
        pass
    finally:
        _file_cache_loaded.add(region)


async def _save_cache(data: dict, cache_path: Path) -> None:
    await aiofiles.os.makedirs(cache_path.parent, exist_ok=True)
    tmp = cache_path.with_suffix(".tmp")
    async with aiofiles.open(tmp, "w", encoding="utf8") as f:
        await f.write(json.dumps(data))
    await aiofiles.os.replace(str(tmp), str(cache_path))


@router.get(
    "",
    summary="Current ranked season",
    description=(
        "Returns the current PJSK ranked season data including the top 100 leaderboard. "
        "`season_status` is one of `going` or `end`. "
        "Data is cached for **5 minutes** - `next_available_update` indicates when fresh data will be available. "
        "If there is no active season, `season_id` will be `null` and no leaderboard data is returned. "
        "If the request fails but cached data exists, the response will include a `cached_data` key with the last successful result."
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
        503: {
            "description": COMMON_RESPONSES[503]["description"],
            "content": {
                "application/json": {
                    "examples": {
                        "no_cache": {
                            "summary": "No cached data available",
                            "value": {"detail": "pjsk_maintainence"},
                        },
                        "with_cache": {
                            "summary": "Cached data available",
                            "value": {
                                "detail": "pjsk_maintainence",
                                "cached_data": {
                                    "updated": 1700000000.0,
                                    "next_available_update": 1700000300.0,
                                    "season_id": 123,
                                    "season_status": "going",
                                    "top_100": {},
                                },
                            },
                        },
                    }
                }
            },
        },
    },
    tags=["PJSK Data"],
)
async def current_ranked(request: Request, region: Literal["en", "jp"]):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    cache_path = client.data_path / "cache" / CACHE_FILE

    if region not in _file_cache_loaded:
        await _try_load_file_cache(region, cache_path)

    prev = cached.get(region, {})
    if prev.get("updated", 0) + CACHE_TTL > time.time():
        return prev

    lock = get_lock(region)

    async with lock:
        prev = cached.get(region, {})
        if prev.get("updated", 0) + CACHE_TTL > time.time():
            return prev

        file_cache = cached.get(region) or None

        try:
            seasons = await client.get_master("rankMatchSeasons")
            season = get_current_season(seasons)

            updated = time.time()

            if not season:
                data = {
                    "updated": updated,
                    "next_available_update": updated + CACHE_TTL,
                    "season_id": None,
                }
                cached[region] = data
                asyncio.create_task(_save_cache(data, cache_path))
                return data

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
            asyncio.create_task(_save_cache(data, cache_path))
            return data

        except HTTPException as e:
            raise HTTPException(
                status_code=e.status_code,
                detail=(
                    {"detail": e.detail, "cached_data": file_cache}
                    if file_cache
                    else e.detail
                ),
            )
