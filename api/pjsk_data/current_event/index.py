from core import SbugaFastAPI

from fastapi import APIRouter, Request, HTTPException, status
from helpers.error_detail_codes import ErrorDetailCode
from pjsk_api.requests import event as pjsk_event_requests
from typing import Literal
import time, asyncio

router = APIRouter()

cached = {}
locks: dict[str, asyncio.Lock] = {}
CACHE_TTL = 300


def get_lock(region: str) -> asyncio.Lock:
    if region not in locks:
        locks[region] = asyncio.Lock()
    return locks[region]


def get_current_event(events: list) -> dict | None:
    now = int(time.time() * 1000)
    for event in events:
        if not event["startAt"] < now < event["closedAt"]:
            continue
        if event["startAt"] < now < event["aggregateAt"]:
            event_status = "going"
        elif event["aggregateAt"] < now < event["aggregateAt"] + 600000:
            event_status = "counting"
        else:
            event_status = "end"
        return {"id": event["id"], "status": event_status}
    return None


@router.get("")
async def current_event(request: Request, region: Literal["en", "jp"]):
    app: SbugaFastAPI = request.app

    prev = cached.get(region, {})
    if prev.get("updated", 0) + CACHE_TTL > time.time():
        return prev

    lock = get_lock(region)

    async with lock:
        # check acquiring lock in case another request just updated it
        prev = cached.get(region, {})
        if prev.get("updated", 0) + CACHE_TTL > time.time():
            return prev

        client = app.pjsk_clients.get(region)
        if not client:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=ErrorDetailCode.InternalServerError.value,
            )

        events = await client.get_master("events")
        event = get_current_event(events)

        updated = time.time()

        if not event:
            return {
                "updated": updated,
                "next_available_update": updated + CACHE_TTL,
                "event_id": None,
            }

        top_100, border = await asyncio.gather(
            app.pjsk_request(
                region, pjsk_event_requests.leaderboard_request(client, event["id"])
            ),
            app.pjsk_request(
                region, pjsk_event_requests.border_request(client, event["id"])
            ),
        )

        data = {
            "updated": updated,
            "next_available_update": updated + CACHE_TTL,
            "event_id": event["id"],
            "event_status": event["status"],
            "top_100": top_100,
            "border": border,
        }
        cached[region] = data

        return data
