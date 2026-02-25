from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
import database as db

router = APIRouter()


@router.get(
    "/{username}",
    summary="Check username availability",
    description="Returns account info if the username is taken, or `404` if it is available.",
    responses={
        200: {
            "description": "Username is taken.",
            "content": {
                "application/json": {
                    "example": {
                        "id": 1234567890,
                        "username": "example",
                        "display_name": "Example",
                    }
                }
            },
        },
        404: {"description": "Username is available."},
    },
    tags=["Account"],
)
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
