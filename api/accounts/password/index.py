from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.passwords import verify_password, hash_password
from helpers import string_checks
from helpers.session import get_session, create_session, Session
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
import database as db

router = APIRouter()


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.post(
    "",
    summary="Change password",
    description="Changes the password for the authenticated account. Requires current password verification. All existing sessions are invalidated and new tokens are returned.",
    responses={
        200: {
            "description": "Password changed successfully.",
            "content": {
                "application/json": {
                    "example": {
                        "access_token": "eyJ...",
                        "refresh_token": "eyJ...",
                    }
                }
            },
        },
        400: {
            "description": f"Invalid new password. (`{ErrorDetailCode.InvalidPassword}`)",
            **ERROR_RESPONSE,
        },
        401: {
            "description": (
                f"Not logged in, token invalid, or old password incorrect. "
                f"(`{ErrorDetailCode.NotLoggedIn}`, `{ErrorDetailCode.SessionExpired}`, "
                f"`{ErrorDetailCode.SessionInvalid}`, `{ErrorDetailCode.InvalidAccountDetails}`)"
            ),
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
async def main(
    request: Request, body: ChangePasswordBody, session: Session = get_session()
):
    app: SbugaFastAPI = request.app

    account_id = session.account_id

    if not string_checks.check_password(body.new_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidPassword.value,
        )

    async with app.acquire_db() as conn:
        account = await conn.fetchrow(db.accounts.get_account_by_id(account_id))

    if not account or not verify_password(body.old_password, account.salted_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.InvalidAccountDetails.value,
        )

    salted_password = hash_password(body.new_password)

    async with app.acquire_db() as conn:
        await conn.execute(
            db.accounts.update_account_password(account_id, salted_password)
        )

    access_token = await create_session(account_id, app, type="access")
    refresh_token = await create_session(account_id, app, type="refresh")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
