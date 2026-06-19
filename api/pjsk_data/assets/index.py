from core import SbugaFastAPI
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import FileResponse
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
from typing import Literal

router = APIRouter()


@router.get(
    "/{asset_path:path}",
    summary="Get asset file",
    description="Returns a raw asset file from the PJSK asset directory for the given region. Use `auto` to search all regions.",
    responses={
        200: {"description": "Asset file bytes"},
        404: {
            "description": f"Asset not found. (`{ErrorDetailCode.NotFound}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["PJSK Assets"],
)
async def get_asset(
    request: Request, region: Literal["en", "jp", "auto"], asset_path: str
):
    app: SbugaFastAPI = request.app

    if region == "auto":
        for r in ["jp", "en"]:
            client = app.pjsk_clients.get(r)
            if not client:
                continue
            file_path = client.data_path / "assets" / asset_path
            try:
                file_path.resolve().relative_to((client.data_path / "assets").resolve())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=ErrorDetailCode.NotFound.value,
                )
            if file_path.exists() and file_path.is_file():
                return FileResponse(file_path)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    file_path = client.data_path / "assets" / asset_path

    try:
        file_path.resolve().relative_to((client.data_path / "assets").resolve())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.NotFound.value,
        )

    return FileResponse(file_path)
