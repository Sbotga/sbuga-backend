from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE
from helpers.session import get_session, Session
import database as db
import asyncio

router = APIRouter()


async def _delete_s3_assets(app: SbugaFastAPI, account_id: int) -> None:
    async with app.s3_session_getter() as s3:
        bucket = await s3.Bucket(app.s3_bucket)

        delete_batches = []
        batch = []

        async for obj in bucket.objects.filter(Prefix=f"{account_id}/"):
            batch.append({"Key": obj.key})
            if len(batch) == 1000:
                delete_batches.append(batch)
                batch = []
        if batch:
            delete_batches.append(batch)

        await asyncio.gather(
            *[bucket.delete_objects(Delete={"Objects": b}) for b in delete_batches]
        )


@router.delete(
    "",
    summary="Delete account",
    description="Permanently deletes the authenticated account and all associated S3 assets. Does not require email verification.",
    responses={
        200: {
            "description": "Account deleted successfully.",
            "content": {"application/json": {"example": {"success": True}}},
        },
        401: {
            "description": f"Not logged in. (`{ErrorDetailCode.NotLoggedIn}`)",
            **ERROR_RESPONSE,
        },
    },
    tags=["Account"],
)
async def delete_account(
    request: Request,
    session: Session = get_session(
        enforce_auth=True,
        allow_unverified_email=True,
        enforce_type=["access", "email_verification"],
    ),
):
    app: SbugaFastAPI = request.app
    user = await session.user()

    await asyncio.gather(
        _delete_s3_assets(app, user.id),
        _delete_db(app, user.id),
    )

    return {"success": True}


async def _delete_db(app: SbugaFastAPI, account_id: int) -> None:
    async with app.acquire_db() as conn:
        await conn.execute(db.accounts.delete_account(account_id))
