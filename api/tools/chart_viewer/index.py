from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from helpers.mirror_chart import mirror
from pjsk_api.asset_handlers.charts import generate_chart_view, score_dir, chart_png
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
        "Returns a PNG image of the chart for a given music ID, difficulty, and region. "
        "If the chart has not been generated yet, it will be generated on first request — this may take a while. "
        "Subsequent requests are served from cache. "
        "`mirrored` flips the lanes horizontally and is never cached."
    ),
    responses={
        200: {"description": "Chart PNG image."},
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
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    padded_id = str(music_id).zfill(4)
    musics = await client.get_master("musics")
    music = next((m for m in musics if m["id"] == music_id), None)
    if not music:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )
    jacket_path = str(
        app.s3_asset_base_url
        + f"/pjsk_data/{region}/music/jacket/"
        + f"{music['assetbundleName']}/{music['assetbundleName']}.png"
    )
    score_path = score_dir(client.data_path, padded_id) / f"{difficulty}.txt"
    png_path = chart_png(client.data_path, padded_id, difficulty)

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
                    musics: list = await client.get_master("musics")
                    music = next((m for m in musics if m["id"] == music_id), None)
                    music_title = music["title"] if music else ""
                except Exception:
                    music_title = ""

                try:
                    await app.run_blocking(
                        generate_chart_view,
                        score_path,
                        png_path,
                        music_title,
                        jacket_path,
                        difficulty,
                    )
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=ErrorDetailCode.InternalServerError.value,
                    )

        await _release_chart_lock(lock_key)

    if mirrored:
        mirrored_bytes = await app.run_blocking(mirror, str(png_path))
        return StreamingResponse(mirrored_bytes, media_type="image/png")

    return FileResponse(png_path, media_type="image/png")
