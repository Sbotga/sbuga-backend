from fastapi import APIRouter, Request
from core import SbugaFastAPI
from helpers.session import get_session, create_session, Session

router = APIRouter()


@router.post("")
async def main(
    request: Request, session: Session = get_session(enforce_type="refresh")
):
    access_token = create_session(session.account_id, type="access")
    return {"token": access_token}
