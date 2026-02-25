from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from database import accounts
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE

router = APIRouter()


@router.get(
    "",
    summary="Get account by username",
    description="Returns public profile information for an account. Banned accounts return `404`. Timestamps are in milliseconds since Unix epoch. `profile_hash` and `banner_hash` may be `null` if not set.",
    responses={
        200: {
            "description": "Account found.",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "id": 1234567890,
                            "display_name": "Example",
                            "username": "example",
                            "created_at": 1700000000000,
                            "updated_at": 1700000000000,
                            "description": "This user hasn't set a description!",
                            "profile_hash": "abc123...",
                            "banner_hash": "abc123...",
                        },
                        "asset_base_url": "https://assets.sbuga.com",
                    }
                }
            },
        },
        404: {
            "description": f"Account not found or banned. (`{ErrorDetailCode.AccountNotFound}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
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
