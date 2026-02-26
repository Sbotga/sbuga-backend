from core import SbugaFastAPI

from fastapi import APIRouter, Request, HTTPException, status
from helpers.erroring import ErrorDetailCode, COMMON_RESPONSES
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


@router.get(
    "",
    summary="Current event",
    description=(
        "Returns the current PJSK event data including the top 100 leaderboard and ranking borders. "
        "`event_status` is one of `going`, `counting`, or `end`. "
        "Data is cached for **5 minutes** - `next_available_update` indicates when fresh data will be available. "
        "If there is no active event, `event_id` will be `null` and no leaderboard or border data is returned."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "examples": {
                        "active": {
                            "summary": "Active event",
                            "value": {
                                "updated": 1700000000.0,
                                "next_available_update": 1700000300.0,
                                "event_id": 123,
                                "event_status": "going",
                                "top_100": {},
                                "border": {},
                            },
                        },
                        "none": {
                            "summary": "No active event",
                            "value": {
                                "updated": 1700000000.0,
                                "next_available_update": 1700000300.0,
                                "event_id": None,
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
async def current_event(request: Request, region: Literal["en", "jp"]):
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
