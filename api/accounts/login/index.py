from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.passwords import verify_password
from helpers.utils import get_ip
from helpers.turnstile import verify_turnstile
import database as db

from helpers.session import create_session

from helpers.error_detail_codes import ErrorDetailCode

router = APIRouter()


class LoginBody(BaseModel):
    username: str
    password: str
    turnstile_response: str


@router.post("")
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

    access_token = create_session(account.id, type="access")
    refresh_token = create_session(account.id, type="refresh")

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
