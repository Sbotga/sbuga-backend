from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
from helpers.session import get_session, Session
from helpers.converter_maps import (
    add_song_alias,
    remove_song_alias,
    add_event_alias,
    remove_event_alias,
)
from helpers.fuzzy_matcher import preprocess
import database as db
from typing import Literal

router = APIRouter()


class AddSongAliasBody(BaseModel):
    music_id: int
    alias: str
    region: Literal["en", "jp"] | None = None


class RemoveSongAliasBody(BaseModel):
    alias_id: int


class AddEventAliasBody(BaseModel):
    event_id: int
    alias: str
    region: Literal["en", "jp"] | None = None


class RemoveEventAliasBody(BaseModel):
    alias_id: int


# Song aliases


@router.post(
    "/song",
    summary="Add song alias",
    description="Adds a new alias for a song. Requires `manage_aliases` permission.",
    responses={
        200: {
            "description": "Alias added.",
            "content": {"application/json": {"example": {"success": True, "id": 1}}},
        },
        403: {
            "description": f"Missing permission. (`{ErrorDetailCode.Forbidden}`)",
            **ERROR_RESPONSE,
        },
        409: {
            "description": f"Alias already exists. (`{ErrorDetailCode.Conflict}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Manage"],
)
async def add_song_alias_route(
    request: Request,
    body: AddSongAliasBody,
    session: Session = get_session(enforce_auth=True),
):
    app: SbugaFastAPI = request.app
    user = await session.user()

    if "manage_aliases" not in session.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorDetailCode.Forbidden.value,
        )

    body.alias = preprocess(body.alias)

    async with app.acquire_db() as conn:
        result = await conn.fetchrow(
            db.aliases.add_song_alias(body.alias, body.music_id, body.region, user.id)
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorDetailCode.Conflict.value,
        )

    add_song_alias(body.alias, body.music_id, body.region)

    return {"success": True, "id": result.id}


@router.delete(
    "/song",
    summary="Remove song alias",
    description="Removes a song alias by ID. Requires `manage_aliases` permission.",
    responses={
        200: {
            "description": "Alias removed.",
            "content": {"application/json": {"example": {"success": True}}},
        },
        403: {
            "description": f"Missing permission. (`{ErrorDetailCode.Forbidden}`)",
            **ERROR_RESPONSE,
        },
        404: {
            "description": f"Alias not found. (`{ErrorDetailCode.NotFound}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Manage"],
)
async def remove_song_alias_route(
    request: Request,
    body: RemoveSongAliasBody,
    session: Session = get_session(enforce_auth=True),
):
    app: SbugaFastAPI = request.app
    await session.user()

    if "manage_aliases" not in session.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorDetailCode.Forbidden.value,
        )

    async with app.acquire_db() as conn:
        existing = await conn.fetchrow(db.aliases.get_song_alias(body.alias_id))
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorDetailCode.NotFound.value,
            )
        await conn.execute(db.aliases.remove_song_alias(body.alias_id))

    remove_song_alias(existing.alias, existing.region)

    return {"success": True}


# Event aliases


@router.post(
    "/event",
    summary="Add event alias",
    description="Adds a new alias for an event. Requires `manage_aliases` permission.",
    responses={
        200: {
            "description": "Alias added.",
            "content": {"application/json": {"example": {"success": True, "id": 1}}},
        },
        403: {
            "description": f"Missing permission. (`{ErrorDetailCode.Forbidden}`)",
            **ERROR_RESPONSE,
        },
        409: {
            "description": f"Alias already exists. (`{ErrorDetailCode.Conflict}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Manage"],
)
async def add_event_alias_route(
    request: Request,
    body: AddEventAliasBody,
    session: Session = get_session(enforce_auth=True),
):
    app: SbugaFastAPI = request.app
    user = await session.user()

    if "manage_aliases" not in session.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorDetailCode.Forbidden.value,
        )

    body.alias = preprocess(body.alias)

    async with app.acquire_db() as conn:
        result = await conn.fetchrow(
            db.aliases.add_event_alias(body.alias, body.event_id, body.region, user.id)
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=ErrorDetailCode.Conflict.value,
        )

    add_event_alias(body.alias, body.event_id, body.region)

    return {"success": True, "id": result.id}


@router.delete(
    "/event",
    summary="Remove event alias",
    description="Removes an event alias by ID. Requires `manage_aliases` permission.",
    responses={
        200: {
            "description": "Alias removed.",
            "content": {"application/json": {"example": {"success": True}}},
        },
        403: {
            "description": f"Missing permission. (`{ErrorDetailCode.Forbidden}`)",
            **ERROR_RESPONSE,
        },
        404: {
            "description": f"Alias not found. (`{ErrorDetailCode.NotFound}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Manage"],
)
async def remove_event_alias_route(
    request: Request,
    body: RemoveEventAliasBody,
    session: Session = get_session(enforce_auth=True),
):
    app: SbugaFastAPI = request.app
    await session.user()

    if "manage_aliases" not in session.permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ErrorDetailCode.Forbidden.value,
        )

    async with app.acquire_db() as conn:
        existing = await conn.fetchrow(db.aliases.get_event_alias(body.alias_id))
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorDetailCode.NotFound.value,
            )
        await conn.execute(db.aliases.remove_event_alias(body.alias_id))

    remove_event_alias(existing.alias, existing.region)

    return {"success": True}


@router.get(
    "/song",
    summary="Get all song aliases",
    description="Returns a list of all song aliases.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "aliases": [
                            {
                                "id": 1,
                                "alias": "tell your world",
                                "music_id": 1,
                                "region": None,
                                "created_at": "2024-01-01T00:00:00",
                                "created_by": None,
                            }
                        ]
                    }
                }
            },
        },
    },
    tags=["Manage"],
)
async def get_song_aliases_route(request: Request):
    app: SbugaFastAPI = request.app
    async with app.acquire_db() as conn:
        aliases = await conn.fetch(db.aliases.get_song_aliases())
    return {"aliases": [a.model_dump() for a in aliases]}


@router.get(
    "/event",
    summary="Get all event aliases",
    description="Returns a list of all event aliases.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "aliases": [
                            {
                                "id": 1,
                                "alias": "wl",
                                "event_id": 1,
                                "region": None,
                                "created_at": "2024-01-01T00:00:00",
                                "created_by": None,
                            }
                        ]
                    }
                }
            },
        },
    },
    tags=["Manage"],
)
async def get_event_aliases_route(request: Request):
    app: SbugaFastAPI = request.app
    async with app.acquire_db() as conn:
        aliases = await conn.fetch(db.aliases.get_event_aliases())
    return {"aliases": [a.model_dump() for a in aliases]}
