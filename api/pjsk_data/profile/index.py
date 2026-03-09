# api/pjsk_data/profile/index.py
from core import SbugaFastAPI
from fastapi import APIRouter, Request, HTTPException, status
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from pjsk_api.requests.profile import profile_request
from typing import Literal
import time
import asyncio

router = APIRouter()

cached: dict[str, dict] = {}  # key: "{region}:{user_id}"
locks: dict[str, asyncio.Lock] = {}
CACHE_TTL = 300


def get_lock(key: str) -> asyncio.Lock:
    if key not in locks:
        locks[key] = asyncio.Lock()
    return locks[key]


def _cleanup_cache():
    now = time.time()
    expired = [k for k, v in cached.items() if v.get("updated", 0) + CACHE_TTL < now]
    for k in expired:
        cached.pop(k, None)
        locks.pop(k, None)


@router.get(
    "/{user_id}",
    summary="PJSK user profile",
    description=(
        "Returns a PJSK user profile by ID. "
        "Data is cached for **5 minutes** - `next_available_update` indicates when fresh data will be available."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "updated": 1700000000.0,
                        "next_available_update": 1700000300.0,
                        "profile": {},
                    }
                }
            },
        },
        404: {
            "description": f"User not found. (`{ErrorDetailCode.NotFound}`)",
            **ERROR_RESPONSE,
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def get_profile(
    request: Request,
    user_id: int,
    region: Literal["en", "jp", "tw", "kr"],
):
    app: SbugaFastAPI = request.app

    asyncio.create_task(asyncio.to_thread(_cleanup_cache))

    cache_key = f"{region}:{user_id}"

    prev = cached.get(cache_key)
    if prev and prev.get("updated", 0) + CACHE_TTL > time.time():
        return prev

    lock = get_lock(cache_key)

    async with lock:
        prev = cached.get(cache_key)
        if prev and prev.get("updated", 0) + CACHE_TTL > time.time():
            return prev

        client = app.pjsk_clients.get(region)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=ErrorDetailCode.PJSKClientUnavailable.value,
            )

        try:
            profile = await app.pjsk_request(region, profile_request(client, user_id))
        except HTTPException as e:
            if e.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorDetailCode.NotFound.value,
                )
            else:
                raise e
        updated = time.time()
        data = {
            "updated": updated,
            "next_available_update": updated + CACHE_TTL,
            "profile": profile,
        }
        cached[cache_key] = data
        return data
