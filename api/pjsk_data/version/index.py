import json
from pathlib import Path

from fastapi import APIRouter, Request, HTTPException, status
from typing import Literal

from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, COMMON_RESPONSES

router = APIRouter()


@router.get(
    "",
    summary="Get data version",
    description="Returns the current master data version and asset version for a given region.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "data_version": "5.3.0.10",
                        "asset_version": "5.3.0.10",
                    }
                }
            },
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def get_version(
    request: Request,
    region: Literal["en", "jp", "tw", "kr"] = "en",
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    data_version_path = client.data_path / "master" / ".dataversion.json"
    asset_version_path = client.data_path / ".assetversion.json"

    data_version = None
    asset_version = None

    if data_version_path.exists():
        with open(data_version_path, "r") as f:
            data = json.load(f)
            data_version = data.get("dataVersion")

    if asset_version_path.exists():
        with open(asset_version_path, "r") as f:
            data = json.load(f)
            asset_version = data.get("assetVersion")

    return {
        "data_version": data_version,
        "asset_version": asset_version,
    }
