from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.passwords import verify_password
from helpers.utils import get_ip
from helpers.turnstile import verify_turnstile
import database as db

from helpers.session import create_session
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE

router = APIRouter()


class LoginBody(BaseModel):
    username: str
    password: str
    turnstile_response: str


USER_EXAMPLE = {
    "id": 1234567890,
    "display_name": "Example",
    "username": "example",
    "created_at": 1700000000000,
    "updated_at": 1700000000000,
    "description": "This user hasn't set a description!",
    "banned": False,
    "profile_hash": None,
    "banner_hash": None,
}


@router.post(
    "",
    summary="Sign in",
    description="Signs into an existing account. Returns the user, access token, refresh token, and asset base URL. Timestamps are in milliseconds since Unix epoch.",
    responses={
        200: {
            "description": "Signed in successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "user": USER_EXAMPLE,
                        "access_token": "eyJ...",
                        "refresh_token": "eyJ...",
                        "asset_base_url": "https://assets.sbuga.com",
                    }
                }
            },
        },
        400: {
            "description": f"Invalid turnstile response. (`{ErrorDetailCode.InvalidTurnstile}`)",
            **ERROR_RESPONSE,
        },
        401: {
            "description": f"Invalid username or password. (`{ErrorDetailCode.InvalidAccountDetails}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Auth"],
)
async def main(request: Request, body: LoginBody):
    app: SbugaFastAPI = request.app

    ip = get_ip(request)
    if not await verify_turnstile(app, body.turnstile_response, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidTurnstile.value,
        )

    async with app.acquire_db() as conn:
        account = await conn.fetchrow(
            db.accounts.get_account_by_username(body.username)
        )

    if not account or not verify_password(body.password, account.salted_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.InvalidAccountDetails.value,
        )

    access_token = await create_session(
        account.id,
        app,
        type="access" if account.email_verified else "email_verification",
        extra={} if account.email_verified else {"email": account.email},
    )
    refresh_token = await create_session(account.id, app, type="refresh")

    return {
        "user": {
            "id": account.id,
            "display_name": account.display_name,
            "username": account.username,
            "created_at": int(account.created_at.timestamp() * 1000),
            "updated_at": int(account.updated_at.timestamp() * 1000),
            "description": account.description,
            "banned": account.banned,
            "profile_hash": account.profile_hash,
            "banner_hash": account.banner_hash,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
        "asset_base_url": app.s3_asset_base_url,
    }
