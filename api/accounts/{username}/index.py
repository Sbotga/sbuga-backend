from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from database import accounts
from helpers.error_detail_codes import ErrorDetailCode

router = APIRouter()


@router.get("")
async def get_account(request: Request, username: str):
    app: SbugaFastAPI = request.app

    async with app.acquire_db() as conn:
        account = await conn.fetchrow(accounts.get_account_by_username(username))

    if not account or account.banned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.AccountNotFound.value,
        )

    return {
        "user": {
            "id": account.id,
            "display_name": account.display_name,
            "username": account.username,
            "created_at": int(account.created_at.timestamp() * 1000),
            "updated_at": int(account.updated_at.timestamp() * 1000),
            "description": account.description,
            "profile_hash": account.profile_hash,
            "banner_hash": account.banner_hash,
        },
        "asset_base_url": app.s3_asset_base_url,
    }
