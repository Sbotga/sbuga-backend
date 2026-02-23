from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI

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
    text_lower = text.lower()

    effective_blocks = [
        w for w in block_words if w.lower() not in [a.lower() for a in allow_words]
    ]

    indexes = []
    for word in effective_blocks:
        word_lower = word.lower()
        start = 0
        while (pos := text_lower.find(word_lower, start)) != -1:
            indexes.append({"start": pos, "end": pos + len(word)})
            start = pos + 1

    indexes.sort(key=lambda x: x["start"])
    merged = []
    for r in indexes:
        if merged and r["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], r["end"])
        else:
            merged.append(r)

    return {"indexes": merged}
