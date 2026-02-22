from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
import database as db

router = APIRouter()


@router.get("/{username}")
async def main(request: Request, username: str):
    app: SbugaFastAPI = request.app

    async with app.acquire_db() as conn:
        account = await conn.fetchrow(db.accounts.get_account_by_username(username))

    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return {
        "id": account.id,
        "username": account.username,
        "display_name": account.display_name,
    }
