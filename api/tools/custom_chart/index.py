import asyncio
import io
import time
import traceback
from collections import OrderedDict
from typing import Literal

import aiohttp
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse

from core import SbugaFastAPI
from helpers.erroring import COMMON_RESPONSES, ERROR_RESPONSE, ErrorDetailCode
from helpers.mirror_chart import mirror
from pjsk_api.asset_handlers.charts import (
    extract_custom_score,
    jacket_source,
    render_custom_chart,
)
from pjsk_api.requests.custom_score import (
    OFFICIAL_BUNDLE_PREFIX,
    download_custom_score,
    download_official_score,
    normalize_pjsk_bytes,
    published_score_request,
)

router = APIRouter()

# metadata changes so it's only cached briefly; the rendered image
# never changes, so it's kept until evicted. Bounded to remove abuse and OOM.
_META_MAX = 500
_META_TTL = 300  # seconds
_IMAGE_MAX = 30

_meta_cache: "OrderedDict[str, tuple[float, dict]]" = OrderedDict()
_image_cache: "OrderedDict[str, bytes]" = OrderedDict()
# combo is counted from the score during image render; a published id is
# immutable, so cache it with no expiry (bounded) and fold it into metadata.
_combo_cache: "OrderedDict[str, int]" = OrderedDict()
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


def _combo_set(key: str, value: int) -> None:
    _combo_cache[key] = value
    _combo_cache.move_to_end(key)
    while len(_combo_cache) > _META_MAX:
        _combo_cache.popitem(last=False)


def _inject_combo(info: dict, key: str) -> None:
    """Fold the known combo count into the metadata (API field wins if it ever
    provides one, else whatever a prior render counted)."""
    combo = _combo_from_info(info)
    if combo is None:
        combo = _combo_cache.get(key)
    if combo is not None:
        info["combo_count"] = combo


async def _normalize_info(client, chart_id: str, info: dict) -> dict | None:
    """Normalize "official" chart maker scores.

    Why does SEGA do this??
    """
    if not isinstance(info, dict):
        return None
    if info.get("userCustomMusicScoreInfoJson"):
        return info

    official = info.get("customMusicScoreOfficialCreatorPublishedResponseJson")
    if not isinstance(official, dict):
        return None

    score_id = official.get("customMusicScoreId") or chart_id
    creators = await client.get_master("customMusicScoreOfficialCreators")
    entry = next((c for c in creators if c.get("scoreId") == score_id), None)
    if not entry:
        return None

    profiles = await client.get_master("customMusicScoreOfficialCreatorProfiles")
    profile_id = entry.get("customMusicScoreOfficialCreatorProfileId")
    profile = next((p for p in profiles if p.get("id") == profile_id), None)
    tags = [entry.get(f"tagId{i}") for i in (1, 2, 3)]

    return {
        "userCustomMusicScoreInfoJson": {
            "userCustomMusicScoreInfoJson": {
                "musicId": entry.get("musicId"),
                "title": entry.get("title"),
                # official scores have no blob path — their data ships as an
                # assetbundle (see _download_official_score)
                "userCustomMusicScorePath": None,
            },
            "userCustomMusicScoreId": score_id,
            "musicDifficultyType": entry.get("musicDifficultyType"),
            "playLevel": entry.get("playLevel"),
            "description": entry.get("description") or "",
            "playCount": official.get("playCount"),
            "fullComboRate": official.get("fullComboRate"),
            "reviewCount": official.get("reviewCount"),
            "publishedAt": entry.get("publishedStartAt"),
            "isDerivativeAllowed": entry.get("isDerivativeAllowed"),
            "customMusicScoreTags": [t for t in tags if t],
        },
        "isOfficialCreator": True,
        "officialScoreBundle": f"{OFFICIAL_BUNDLE_PREFIX}/{score_id}",
        "officialCreator": {
            "profileId": profile_id,
            "name": profile.get("name") if profile else None,
            "previewStartTimeSec": entry.get("previewStartTimeSec"),
        },
    }


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
        "return the chart image (png). Pass `chart_data=true` to instead return only the chart raw data."
        "Metadata is cached briefly; rendered images are cached (they never change)."
    ),
    responses={
        200: {"description": "Chart metadata (json) or chart image (png)."},
        400: {"description": "Passed both chart_image and chart_data as true."},
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
    chart_data: bool = False,
    mirrored: bool = False,
):
    app: SbugaFastAPI = request.app

    if chart_image and chart_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.BadRequestFields.value,
        )

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
            print(f"[custom_chart] metadata fetch failed for {key}: {e.status} {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=ErrorDetailCode.InternalServerError.value,
            )
        # user scores and official-creator scores come back in different shapes
        info = await _normalize_info(client, chart_id, info)
        if info is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorDetailCode.NotFound.value,
            )
        info["refreshed_at"] = int(time.time())  # when this metadata was fetched
        _meta_set(key, info)

    _inject_combo(info, key)

    if not (chart_image or chart_data):
        return JSONResponse(content=info)

    level1 = info.get("userCustomMusicScoreInfoJson") or {}
    inner = level1.get("userCustomMusicScoreInfoJson") or {}

    if info.get("isOfficialCreator"):
        # official scores live in an assetbundle, not the blob API
        score_id = level1.get("userCustomMusicScoreId") or chart_id
        bundle = await download_official_score(client, score_id)
        raw = await app.run_blocking(extract_custom_score, bundle)
    else:
        score_path = inner.get("userCustomMusicScorePath")
        if not score_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorDetailCode.NotFound.value,
            )
        raw = await download_custom_score(client, score_path)

    # --- chart image (cached, no expiry; mirrored is a separate entry) ---
    if chart_image:
        img_key = f"{key}:{int(mirrored)}"
        img = _image_get(img_key)
        if img is None:
            lock = await _render_lock(img_key)
            async with lock:
                img = _image_get(img_key)
                if img is None:
                    img = await _build_image(
                        app, client, region, raw, chart_id, info, mirrored
                    )
                    _image_set(img_key, img)
        return StreamingResponse(io.BytesIO(img), media_type="image/png")
    else:
        return StreamingResponse(io.BytesIO(raw), media_type="application/octet-stream")


def _combo_from_info(info: dict) -> int | None:
    """combo_count if the API provided one (it doesn't today), else whatever a
    prior image render computed and cached onto the metadata."""
    level1 = info.get("userCustomMusicScoreInfoJson") or {}
    for key in ("noteCount", "comboCount", "combo_count"):
        if level1.get(key) is not None:
            return level1[key]
    return info.get("combo_count")


async def _build_image(
    app: SbugaFastAPI,
    client,
    region: str,
    raw: bytes,
    chart_id: str,
    info: dict,
    mirrored: bool,
) -> bytes:
    level1 = info.get("userCustomMusicScoreInfoJson") or {}
    inner = level1.get("userCustomMusicScoreInfoJson") or {}

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
        data = normalize_pjsk_bytes(raw)
        png, combo = await app.run_blocking(
            render_custom_chart,
            data,
            title=title,
            difficulty=difficulty,
            playlevel=str(playlevel) if playlevel is not None else None,
            jacket=jacket,
            chart_id=f"{region.upper()}: {chart_id}",
        )
        # the API doesn't return a combo count, so cache the one we counted from
        # the score (immutable per id) for the metadata endpoint to serve
        _combo_set(f"{region}:{chart_id}", combo)
        if mirrored:
            png = (await app.run_blocking(mirror, io.BytesIO(png))).getvalue()
        return png
    except HTTPException:
        raise
    except Exception:
        print(f"[custom_chart] render failed for {region}:{chart_id}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ErrorDetailCode.InternalServerError.value,
        )
