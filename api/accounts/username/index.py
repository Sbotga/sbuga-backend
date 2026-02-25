from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.passwords import verify_password
from helpers import string_checks
from helpers.session import get_session, Session
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
import database as db

router = APIRouter()


class ChangeUsernameBody(BaseModel):
    password: str
    new_username: str


@router.post(
    "",
    summary="Change username",
    description="Changes the username for the authenticated account. Requires current password verification.",
    responses={
        200: {
            "description": "Username changed successfully.",
            "content": {"application/json": {"example": {"username": "new_username"}}},
        },
        400: {
            "description": f"Invalid new username. (`{ErrorDetailCode.InvalidUsername}`)",
            **ERROR_RESPONSE,
        },
        401: {
            "description": f"Not logged in or password incorrect. (`{ErrorDetailCode.NotLoggedIn}`, `{ErrorDetailCode.SessionExpired}`, `{ErrorDetailCode.SessionInvalid}`, `{ErrorDetailCode.InvalidAccountDetails}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
async def main(
    request: Request, body: ChangeUsernameBody, session: Session = get_session()
):
    app: SbugaFastAPI = request.app

    account_id = session.account_id

    if not string_checks.check_username(body.new_username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidUsername.value,
        )

    async with app.acquire_db() as conn:
        account = await conn.fetchrow(db.accounts.get_account_by_id(account_id))

    if not account or not verify_password(body.password, account.salted_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ErrorDetailCode.InvalidAccountDetails.value,
        )

    async with app.acquire_db() as conn:
        await conn.execute(
            db.accounts.update_account_username(account_id, body.new_username)
        )

    return {"username": body.new_username}
