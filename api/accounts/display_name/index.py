from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers import string_checks
from helpers.session import get_session, Session
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
import database as db

router = APIRouter()


class ChangeDisplaynameBody(BaseModel):
    new_display_name: str


@router.post(
    "",
    summary="Change display name",
    description="Changes the display name for the authenticated account.",
    responses={
        200: {
            "description": "Display name changed successfully.",
            "content": {
                "application/json": {"example": {"display_name": "New Display Name"}}
            },
        },
        400: {
            "description": f"Invalid new display name. (`{ErrorDetailCode.InvalidDisplayName}`)",
            **ERROR_RESPONSE,
        },
        401: {
            "description": (
                f"Not logged in or token invalid. "
                f"(`{ErrorDetailCode.NotLoggedIn}`, `{ErrorDetailCode.SessionExpired}`, `{ErrorDetailCode.SessionInvalid}`)"
            ),
            **ERROR_RESPONSE,
        },
        404: {
            "description": f"Account not found. (`{ErrorDetailCode.AccountNotFound}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
async def main(
    request: Request, body: ChangeDisplaynameBody, session: Session = get_session()
):
    app: SbugaFastAPI = request.app

    account_id = session.account_id

    if not string_checks.check_display_name(body.new_display_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidDisplayName.value,
        )

    async with app.acquire_db() as conn:
        account = await conn.fetchrow(db.accounts.get_account_by_id(account_id))

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ErrorDetailCode.AccountNotFound.value,
        )

    async with app.acquire_db() as conn:
        await conn.execute(
            db.accounts.update_account_display_name(account_id, body.new_display_name)
        )

    return {"display_name": body.new_display_name}
