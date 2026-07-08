import asyncio
import io
import time
from collections import OrderedDict
from typing import Literal

import aiohttp
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from core import SbugaFastAPI
from helpers.erroring import COMMON_RESPONSES, ERROR_RESPONSE, ErrorDetailCode
from pjsk_api.asset_handlers.charts import jacket_source, render_custom_chart
from pjsk_api.requests.custom_score import (
    download_custom_score,
    normalize_pjsk_bytes,
    published_score_request,
)

router = APIRouter()

# metadata changes so it's only cached briefly; the rendered image
# never changes, so it's kept until evicted. Bounded to remove abuse and OOM.
_META_MAX = 500
_META_TTL = 300  # seconds
_IMAGE_MAX = 20

_meta_cache: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_image_cache: "OrderedDict[str, bytes]" = OrderedDict()
_render_locks: dict[str, asyncio.Lock] = {}
_render_locks_meta = asyncio.Lock()


def _meta_get(key: str) -> dict | None:
    entry = _meta_cache.get(key)
    if entry is None:
        return None
    ts, value = entry
    if time.monotonic() - ts > _META_TTL:
        _meta_cache.pop(key, None)
        return None
    _meta_cache.move_to_end(key)
    return value


def _meta_set(key: str, value: dict) -> None:
    _meta_cache[key] = (time.monotonic(), value)
    _meta_cache.move_to_end(key)
    while len(_meta_cache) > _META_MAX:
        _meta_cache.popitem(last=False)


def _image_get(key: str) -> bytes | None:
    img = _image_cache.get(key)
    if img is not None:
        _image_cache.move_to_end(key)
    return img


def _image_set(key: str, value: bytes) -> None:
    _image_cache[key] = value
    _image_cache.move_to_end(key)
    while len(_image_cache) > _IMAGE_MAX:
        _image_cache.popitem(last=False)


async def _render_lock(key: str) -> asyncio.Lock:
    async with _render_locks_meta:
        lock = _render_locks.get(key)
        if lock is None:
            lock = _render_locks[key] = asyncio.Lock()
        return lock


@router.get(
    "",
    summary="Get a custom chart by id",
    description=(
        "Fetches a published custom chart's metadata by id. By default returns "
        "the raw metadata JSON; pass `chart_image=true` to instead render and "
        "return the chart image (png). Metadata is cached briefly; rendered "
        "images are cached (they never change)."
    ),
    responses={
        200: {"description": "Chart metadata (json) or chart image (png)."},
        404: {
            "description": f"Chart not found. (`{ErrorDetailCode.NotFound}`)",
            **ERROR_RESPONSE,
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Tools"],
)
async def get_custom_chart(
    request: Request,
    chart_id: str,
    region: Literal["jp"],  # only jp exists atm
    chart_image: bool = False,
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    key = f"{region}:{chart_id}"

    # --- metadata (cached 5 min) ---
    info = _meta_get(key)
    if info is None:
        try:
            info = await app.pjsk_request(
                region, published_score_request(client, chart_id)
            )
        except aiohttp.ClientResponseError as e:
            if e.status == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorDetailCode.NotFound.value,
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorDetailCode.InternalServerError.value,
            )
        if not isinstance(info, dict) or not info.get("userCustomMusicScoreInfoJson"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorDetailCode.NotFound.value,
            )
        _meta_set(key, info)

    if not chart_image:
        return JSONResponse(content=info)

    # --- chart image (cached, no expiry) ---
    img = _image_get(key)
    if img is None:
        lock = await _render_lock(key)
        async with lock:
            img = _image_get(key)
            if img is None:
                img = await _build_image(app, client, region, chart_id, info)
                _image_set(key, img)

    return StreamingResponse(io.BytesIO(img), media_type="image/png")


async def _build_image(
    app: SbugaFastAPI, client, region: str, chart_id: str, info: dict
) -> bytes:
    level1 = info.get("userCustomMusicScoreInfoJson") or {}
    inner = level1.get("userCustomMusicScoreInfoJson") or {}
    score_path = inner.get("userCustomMusicScorePath")
    if not score_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )

    title = inner.get("title") or ""
    music_id = inner.get("musicId")
    difficulty = level1.get("musicDifficultyType")
    playlevel = level1.get("playLevel")

    jacket = ""
    if music_id is not None:
        musics = await client.get_master("musics")
        music = next((m for m in musics if m.get("id") == music_id), None)
        jacket = jacket_source(client.data_path, app.s3_asset_base_url, region, music)

    try:
        raw = await download_custom_score(client, score_path)
        data = normalize_pjsk_bytes(raw)
        return await app.run_blocking(
            render_custom_chart,
            data,
            title=title,
            difficulty=difficulty,
            playlevel=str(playlevel) if playlevel is not None else None,
            jacket=jacket,
            chart_id=chart_id,
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorDetailCode.InternalServerError.value,
        )
