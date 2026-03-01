from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.passwords import hash_password
from helpers.utils import get_ip
from helpers.turnstile import verify_turnstile
from helpers import string_checks
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
import database as db
import time, secrets

from helpers.session import create_session
from helpers import emails

router = APIRouter()


class SignupBody(BaseModel):
    display_name: str
    username: str
    email: str
    password: str
    turnstile_response: str


USER_EXAMPLE = {
    "id": 1234567890,
    "email": "dev@sbuga.com",
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
    summary="Sign up",
    description="Creates a new account. Returns the created user, access token, refresh token, and asset base URL. Timestamps are in milliseconds since Unix epoch.",
    responses={
        200: {
            "description": "Account created successfully.",
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
            "description": (
                f"Validation error. "
                f"(`{ErrorDetailCode.InvalidTurnstile}`, "
                f"`{ErrorDetailCode.InvalidUsername}`, "
                f"`{ErrorDetailCode.InvalidPassword}`, "
                f"`{ErrorDetailCode.InvalidDisplayName}`, "
                f"`{ErrorDetailCode.InvalidEmail}`)"
            ),
            **ERROR_RESPONSE,
        },
        409: {
            "description": f"Username or email already taken. (`{ErrorDetailCode.UsernameConflict}`, `{ErrorDetailCode.EmailConflict}`)",
            **ERROR_RESPONSE,
        },
        500: {
            "description": f"Internal error, e.g. rare account ID collision. (`{ErrorDetailCode.InternalServerError}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Auth"],
)
async def main(request: Request, body: SignupBody):
    app: SbugaFastAPI = request.app

    ip = get_ip(request)
    if not await verify_turnstile(app, body.turnstile_response, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidTurnstile.value,
        )

    if not emails.check_email(body.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidEmail.value,
        )
    if not string_checks.check_username(body.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidUsername.value,
        )
    if not string_checks.check_display_name(body.display_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidDisplayName.value,
        )
    if not string_checks.check_password(body.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidPassword.value,
        )

    async with app.acquire_db() as conn:
        existing = await conn.fetchrow(
            db.accounts.get_account_by_username(body.username)
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorDetailCode.UsernameConflict.value,
            )
        existing_email = await conn.fetchrow(
            db.accounts.get_account_by_base_email(emails.get_base_email(body.email))
        )
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ErrorDetailCode.EmailConflict.value,
            )

    now = time.time()
    now_ms = int(now * 1000)

    epoch_offset = 1600218000000
    timestamp_bits = now_ms - epoch_offset
    random_bits = secrets.randbits(22)
    account_id = (timestamp_bits << 22) | random_bits
    salted_password = hash_password(body.password)

    async with app.acquire_db() as conn:
        await conn.execute(
            db.accounts.create_account(
                account_id,
                body.email,
                body.display_name,
                body.username,
                salted_password,
            )
        )
        account = await conn.fetchrow(db.accounts.get_account_by_id(account_id))

    access_token = await create_session(
        account_id, app, type="email_verification", extra={"email": account.email}
    )
    refresh_token = await create_session(account_id, app, type="refresh")

    return {
        "user": {
            "id": account.id,
            "email": account.email,
            "display_name": account.display_name,
            "username": account.username,
            "created_at": now_ms,
            "updated_at": now_ms,
            "description": account.description,
            "banned": account.banned,
            "profile_hash": account.profile_hash,
            "banner_hash": account.banner_hash,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
        "asset_base_url": app.s3_asset_base_url,
    }
