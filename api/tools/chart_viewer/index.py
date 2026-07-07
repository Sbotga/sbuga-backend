from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import StreamingResponse, RedirectResponse
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from helpers.mirror_chart import mirror
from pjsk_api.asset_handlers.charts import (
    chart_file,
    generate_chart_view,
    jacket_source,
    score_dir,
)
from typing import Literal
import asyncio

router = APIRouter()

_chart_locks: dict[str, asyncio.Lock] = {}
_chart_locks_meta = asyncio.Lock()


async def _get_chart_lock(key: str) -> asyncio.Lock:
    async with _chart_locks_meta:
        if key not in _chart_locks:
            _chart_locks[key] = asyncio.Lock()
        return _chart_locks[key]


async def _release_chart_lock(key: str) -> None:
    async with _chart_locks_meta:
        _chart_locks.pop(key, None)


@router.get(
    "",
    summary="Get chart image",
    description=(
        "Chart image for a music ID / difficulty / region. Un-mirrored charts "
        "302-redirect to the pre-rendered file on R2 (in the requested "
        "`image_type`). `mirrored` flips the lanes horizontally — those are "
        "loaded and edited per-request (never cached). Charts not yet rendered "
        "are generated on first request."
    ),
    responses={
        200: {"description": "Chart image (mirrored)."},
        307: {"description": "Redirect to the chart on R2 (un-mirrored)."},
        404: {
            "description": f"Chart or music not found. (`{ErrorDetailCode.NotFound}`)",
            **ERROR_RESPONSE,
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Tools"],
)
async def get_chart(
    request: Request,
    music_id: int,
    difficulty: Literal["easy", "normal", "hard", "expert", "master", "append"],
    region: Literal["en", "jp"],
    mirrored: bool = False,
    image_type: Literal["webp", "png"] = "png",
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    padded_id = str(music_id).zfill(4)

    # un-mirrored: redirect to the pre-rendered chart on R2
    if not mirrored:
        return RedirectResponse(
            f"{app.s3_asset_base_url}/pjsk_data/{region}"
            f"/music/music_score/{padded_id}_01/{difficulty}.{image_type}"
        )

    # mirrored: load the local chart (rendering it if missing) and flip it
    musics = await client.get_master("musics")
    music = next((m for m in musics if m["id"] == music_id), None)
    if not music:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )
    jacket_path = jacket_source(client.data_path, app.s3_asset_base_url, region, music)
    score_path = score_dir(client.data_path, padded_id) / f"{difficulty}.txt"
    png_path = chart_file(client.data_path, padded_id, difficulty, "png")

    if not score_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )

    if not png_path.exists():
        lock_key = f"{region}:{padded_id}:{difficulty}"
        chart_lock = await _get_chart_lock(lock_key)
        async with chart_lock:
            if not png_path.exists():
                try:
                    await app.run_blocking(
                        generate_chart_view,
                        score_path,
                        score_dir(client.data_path, padded_id),
                        difficulty,
                        music["title"],
                        jacket_path,
                        difficulty,
                    )
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=ErrorDetailCode.InternalServerError.value,
                    )
        await _release_chart_lock(lock_key)

    mirrored_bytes = await app.run_blocking(mirror, str(png_path))
    return StreamingResponse(mirrored_bytes, media_type="image/png")
