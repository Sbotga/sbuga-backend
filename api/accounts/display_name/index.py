from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers import string_checks
from helpers.session import get_session, Session
from helpers.error_detail_codes import ErrorDetailCode
import database as db

router = APIRouter()


class ChangeDisplaynameBody(BaseModel):
    new_display_name: str


@router.post("")
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
