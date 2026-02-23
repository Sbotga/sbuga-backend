from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.passwords import hash_password
from helpers.utils import get_ip
from helpers.turnstile import verify_turnstile
from helpers import string_checks
from helpers.error_detail_codes import ErrorDetailCode
import database as db
import time, secrets

from helpers.session import create_session

router = APIRouter()


class SignupBody(BaseModel):
    display_name: str
    username: str
    password: str
    turnstile_response: str


@router.post("")
async def main(request: Request, body: SignupBody):
    app: SbugaFastAPI = request.app

    ip = get_ip(request)
    if not await verify_turnstile(app, body.turnstile_response, ip):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidTurnstile.value,
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

    now = time.time()
    now_ms = int(now * 1000)

    epoch_offset = 1600218000000  # same as pjsk lol
    timestamp_bits = now_ms - epoch_offset  # first 42 bits
    # Randomize the last 22 bits
    random_bits = secrets.randbits(22)
    account_id = (timestamp_bits << 22) | random_bits
    # ^ chance of collision is negligible, but exists.
    # in that case, the db will error for us and return 500
    # no need to worry about duplicates! :troll:
    salted_password = hash_password(body.password)

    async with app.acquire_db() as conn:
        await conn.execute(
            db.accounts.create_account(
                account_id, body.display_name, body.username, salted_password
            )
        )

        account = await conn.fetchrow(db.accounts.get_account_by_id(account_id))

    access_token = create_session(account_id, type="access")
    refresh_token = create_session(account_id, type="refresh")

    return {
        "user": {
            "id": account.id,
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
