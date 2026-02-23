from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.error_detail_codes import ErrorDetailCode

import re2

from typing import Literal

router = APIRouter()


class CheckWordsBody(BaseModel):
    text: str
    region: Literal["en", "jp"]


MAX_TEXT_LENGTH = 1024


@router.get("")
async def main(request: Request, body: CheckWordsBody):
    app: SbugaFastAPI = request.app
    client = app.pjsk_clients[body.region]

    if len(body.text) > MAX_TEXT_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorDetailCode.TooMuchData.value,
        )

    try:
        allow_words: list = await client.get_master("allowWords")
    except FileNotFoundError:
        allow_words = []

    block_words: list = await client.get_master("ngWords")

    text = body.text

    allowed_patterns = [re2.escape(a["word"]) for a in allow_words]
    if allowed_patterns:
        scrubbed = re2.sub(f"(?i)({'|'.join(allowed_patterns)})", "", text)
    else:
        scrubbed = text

    indexes = []
    for block in block_words:
        word = re2.escape(block["word"])
        for match in re2.finditer(f"(?i){word}", scrubbed):
            indexes.append({"start": match.start(), "end": match.end()})

    indexes.sort(key=lambda x: x["start"])
    merged = []
    for r in indexes:
        if merged and r["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], r["end"])
        else:
            merged.append(r)

    return {"indexes": merged}
