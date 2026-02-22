from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.passwords import verify_password, hash_password
from helpers import string_checks
from helpers.session import get_session, Session
from helpers.error_detail_codes import ErrorDetailCode
import database as db

router = APIRouter()


class ChangePasswordBody(BaseModel):
    old_password: str
    new_password: str


@router.post("")
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

    return {}
