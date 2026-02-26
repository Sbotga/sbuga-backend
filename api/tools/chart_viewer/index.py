from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from helpers.mirror_chart import mirror
from typing import Literal
from pathlib import Path
from threading import Lock
import asyncio
import subprocess
import sys
import sekaiworld.scores as scores

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


def _generate_svg(
    score_path: Path,
    svg_path: Path,
    music_title: str,
    jacket_path: str,
    difficulty: str,
) -> None:
    score = scores.Score.open(str(score_path), encoding="utf-8")
    score.meta.title = music_title
    score.meta.jacket = jacket_path
    score.meta.difficulty = difficulty
    drawing = scores.Drawing(score)
    svg = drawing.svg()
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg.saveas(str(svg_path))


def _generate_png_subprocess(svg_path: Path, png_path: Path) -> None:
    command = [sys.executable, "helpers/svg_to_png.py", str(svg_path), str(png_path)]

    kwargs = dict(
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )

    proc = subprocess.Popen(command, **kwargs)
    try:
        proc.wait(timeout=600)
        if proc.returncode != 0:
            raise RuntimeError(
                f"svg_to_png subprocess failed with code {proc.returncode}"
            )
    except subprocess.TimeoutExpired:
        proc.kill()
        raise RuntimeError("svg_to_png subprocess timed out")


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
            detail=ErrorDetailCode.InternalServerError.value,
        )

    padded_id = str(music_id).zfill(4)
    padded_id_3 = str(music_id).zfill(3)
    jacket_path = str(
        app.base_url
        + "/api/pjsk_data/assets/music/jacket"
        + f"/jacket_s_{padded_id_3}"
        + f"/jacket_s_{padded_id_3}.png?region={region}"
    )
    score_path = (
        client.data_path
        / "assets"
        / "music"
        / "music_score"
        / f"{padded_id}_01"
        / f"{difficulty}.txt"
    )
    svg_path = (
        client.data_path / "music_score_view" / f"{padded_id}_01" / f"{difficulty}.svg"
    )
    png_path = svg_path.with_suffix(".png")

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
                        _generate_svg,
                        score_path,
                        svg_path,
                        music_title,
                        jacket_path,
                        difficulty.upper(),
                    )
                except Exception:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=ErrorDetailCode.NotFound.value,
                    )

                try:
                    await app.run_blocking(_generate_png_subprocess, svg_path, png_path)
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
