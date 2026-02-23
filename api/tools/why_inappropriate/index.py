from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI

import re2

from typing import Literal

router = APIRouter()


class CheckWordsBody(BaseModel):
    text: str
    region: Literal["en", "jp"]


@router.get("")
async def main(request: Request, body: CheckWordsBody):
    app: SbugaFastAPI = request.app
    client = app.pjsk_clients[body.region]

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
