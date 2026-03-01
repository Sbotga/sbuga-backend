from core import SbugaFastAPI
from fastapi import APIRouter, Request, HTTPException, status, UploadFile
from pydantic import BaseModel
from database import accounts
from helpers.session import get_session, Session
from helpers.hashing import calculate_sha256
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from PIL import Image
import io

router = APIRouter()

PROFILE_SIZE = (400, 400)
BANNER_SIZE = (1200, 360)

AUTH_RESPONSES = {
    401: COMMON_RESPONSES[401],
}

SUCCESS_RESPONSE = {
    200: {
        "description": "Success",
        "content": {"application/json": {"example": {"result": "success"}}},
    }
}


class UpdateDescriptionBody(BaseModel):
    description: str


async def _convert_images(
    app: SbugaFastAPI, content: bytes, size: tuple
) -> tuple[bytes, bytes]:
    def convert(content: bytes) -> tuple[bytes, bytes]:
        image = Image.open(io.BytesIO(content))
        image = image.convert("RGB")
        image = image.resize(size, Image.Resampling.LANCZOS)

        png_buffer = io.BytesIO()
        image.save(png_buffer, format="PNG")

        webp_buffer = io.BytesIO()
        image.save(webp_buffer, format="WEBP")

        return png_buffer.getvalue(), webp_buffer.getvalue()

    try:
        return await app.run_blocking(convert, content)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.InvalidImage.value,
        )


async def _delete_s3_prefix(app: SbugaFastAPI, prefix: str):
    async with app.s3_session_getter() as s3:
        bucket = await s3.Bucket(app.s3_bucket)
        batch = []
        async for obj in bucket.objects.filter(Prefix=prefix):
            batch.append({"Key": obj.key})
            if len(batch) == 1000:
                await bucket.delete_objects(Delete={"Objects": batch})
                batch = []
        if batch:
            await bucket.delete_objects(Delete={"Objects": batch})


async def _upload_s3(app: SbugaFastAPI, png_bytes: bytes, webp_bytes: bytes, path: str):
    async with app.s3_session_getter() as s3:
        bucket = await s3.Bucket(app.s3_bucket)
        await bucket.upload_fileobj(
            Fileobj=io.BytesIO(png_bytes),
            Key=path,
            ExtraArgs={"ContentType": "image/png"},
        )
        await bucket.upload_fileobj(
            Fileobj=io.BytesIO(webp_bytes),
            Key=f"{path}_webp",
            ExtraArgs={"ContentType": "image/webp"},
        )


@router.get(
    "/me",
    summary="Get own account",
    description="Returns the authenticated account's full profile information. Timestamps are in milliseconds since Unix epoch. `profile_hash` and `banner_hash` may be `null` if not set.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "user": {
                            "id": 1234567890,
                            "email": "dev@sbuga.com",
                            "email_verified": True,
                            "display_name": "Example",
                            "username": "example",
                            "created_at": 1700000000000,
                            "updated_at": 1700000000000,
                            "description": "This user hasn't set a description!",
                            "profile_hash": "abc123...",
                            "banner_hash": "abc123...",
                            "banned": False,
                        },
                        "asset_base_url": "https://assets.sbuga.com",
                    }
                }
            },
        },
        **AUTH_RESPONSES,
    },
    tags=["Account"],
)
async def get_self(
    request: Request,
    session: Session = get_session(enforce_type=["access", "email_verification"]),
):
    app: SbugaFastAPI = request.app
    account = await session.user()

    return {
        "user": {
            "id": account.id,
            "display_name": account.display_name,
            "email": account.email,
            "email_verified": account.email_verified,
            "username": account.username,
            "created_at": int(account.created_at.timestamp() * 1000),
            "updated_at": int(account.updated_at.timestamp() * 1000),
            "description": account.description,
            "profile_hash": account.profile_hash,
            "banner_hash": account.banner_hash,
            "banned": account.banned,
        },
        "asset_base_url": app.s3_asset_base_url,
    }


@router.delete(
    "/profile",
    summary="Delete profile picture",
    description="Deletes the authenticated account's profile picture.",
    responses={**SUCCESS_RESPONSE, **AUTH_RESPONSES},
    tags=["Account"],
)
async def delete_profile(request: Request, session: Session = get_session()):
    app: SbugaFastAPI = request.app
    user = await session.user()

    await _delete_s3_prefix(app, f"{user.id}/profile/")

    async with app.acquire_db() as conn:
        await conn.execute(accounts.update_profile_hash(user.id, None))

    return {"result": "success"}


@router.delete(
    "/banner",
    summary="Delete banner",
    description="Deletes the authenticated account's banner.",
    responses={**SUCCESS_RESPONSE, **AUTH_RESPONSES},
    tags=["Account"],
)
async def delete_banner(request: Request, session: Session = get_session()):
    app: SbugaFastAPI = request.app
    user = await session.user()

    await _delete_s3_prefix(app, f"{user.id}/banner/")

    async with app.acquire_db() as conn:
        await conn.execute(accounts.update_banner_hash(user.id, None))

    return {"result": "success"}


@router.post(
    "/description",
    summary="Update description",
    description="Updates the authenticated account's description.",
    responses={**SUCCESS_RESPONSE, **AUTH_RESPONSES},
    tags=["Account"],
)
async def update_description(
    request: Request, body: UpdateDescriptionBody, session: Session = get_session()
):
    app: SbugaFastAPI = request.app
    user = await session.user()

    async with app.acquire_db() as conn:
        await conn.execute(accounts.update_description(user.id, body.description))

    return {"result": "success"}


@router.post(
    "/profile/upload",
    summary="Upload profile picture",
    description="Uploads a profile picture for the authenticated account. Image will be resized to 400x400 and saved as PNG and WebP. Max size: **10MB**.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {"result": "success", "hash": "abc123..."}
                }
            },
        },
        400: {
            "description": f"Invalid image file. (`{ErrorDetailCode.InvalidImage}`)",
            **ERROR_RESPONSE,
        },
        413: {
            "description": f"File size exceeds 10MB limit. (`{ErrorDetailCode.FileTooLarge}`)",
            **ERROR_RESPONSE,
        },
        **AUTH_RESPONSES,
    },
    tags=["Account"],
)
async def upload_profile(
    request: Request, file: UploadFile, session: Session = get_session()
):
    app: SbugaFastAPI = request.app
    user = await session.user()

    file_content = await file.read()
    if len(file_content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=ErrorDetailCode.FileTooLarge.value,
        )

    png_bytes, webp_bytes = await _convert_images(app, file_content, PROFILE_SIZE)
    file_hash = calculate_sha256(png_bytes)

    await _delete_s3_prefix(app, f"{user.id}/profile/")
    await _upload_s3(app, png_bytes, webp_bytes, f"{user.id}/profile/{file_hash}")

    async with app.acquire_db() as conn:
        await conn.execute(accounts.update_profile_hash(user.id, file_hash))

    return {"result": "success", "hash": file_hash}


@router.post(
    "/banner/upload",
    summary="Upload banner",
    description="Uploads a banner for the authenticated account. Image will be resized to 1200x360 and saved as PNG and WebP. Max size: **15MB**.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {"result": "success", "hash": "abc123..."}
                }
            },
        },
        400: {
            "description": f"Invalid image file. (`{ErrorDetailCode.InvalidImage}`)",
            **ERROR_RESPONSE,
        },
        413: {
            "description": f"File size exceeds 15MB limit. (`{ErrorDetailCode.FileTooLarge}`)",
            **ERROR_RESPONSE,
        },
        **AUTH_RESPONSES,
    },
    tags=["Account"],
)
async def upload_banner(
    request: Request, file: UploadFile, session: Session = get_session()
):
    app: SbugaFastAPI = request.app
    user = await session.user()

    file_content = await file.read()
    if len(file_content) > 15 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=ErrorDetailCode.FileTooLarge.value,
        )

    png_bytes, webp_bytes = await _convert_images(app, file_content, BANNER_SIZE)
    file_hash = calculate_sha256(png_bytes)

    await _delete_s3_prefix(app, f"{user.id}/banner/")
    await _upload_s3(app, png_bytes, webp_bytes, f"{user.id}/banner/{file_hash}")

    async with app.acquire_db() as conn:
        await conn.execute(accounts.update_banner_hash(user.id, file_hash))

    return {"result": "success", "hash": file_hash}
