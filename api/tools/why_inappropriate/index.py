from fastapi import APIRouter, Request, HTTPException, status
from pydantic import BaseModel
from core import SbugaFastAPI
from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES

import re2

from typing import Literal

router = APIRouter()


class CheckWordsBody(BaseModel):
    text: str
    region: Literal["en", "jp"]


MAX_TEXT_LENGTH = 1024


@router.post(
    "",
    summary="Check inappropriate text",
    description=(
        "Returns the character index ranges of inappropriate text based on PJSK's "
        "block and allow word lists for a given region. "
        "`start` and `end` are indexes (0 based, inclusive) text. "
        "Overlapping ranges are merged. An empty array means the text is clean."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "indexes": [
                            {"start": 0, "end": 5},
                            {"start": 12, "end": 20},
                        ]
                    }
                }
            },
        },
        400: {
            "description": f"Text too long (`{ErrorDetailCode.TooMuchData}`) or invalid request (`{ErrorDetailCode.BadRequestFields}`).",
            **ERROR_RESPONSE,
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Tools"],
)
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
    allowed_ranges = []
    if allowed_patterns:
        for match in re2.finditer(f"(?i)({'|'.join(allowed_patterns)})", text):
            allowed_ranges.append((match.start(), match.end()))

    def is_allowed(start, end):
        return any(
            a_start <= start and end <= a_end for a_start, a_end in allowed_ranges
        )

    indexes = []
    for block in block_words:
        word = re2.escape(block["word"])
        for match in re2.finditer(f"(?i){word}", text):
            if not is_allowed(match.start(), match.end()):
                indexes.append({"start": match.start(), "end": match.end()})

    indexes.sort(key=lambda x: x["start"])
    merged = []
    for r in indexes:
        if merged and r["start"] <= merged[-1]["end"]:
            merged[-1]["end"] = max(merged[-1]["end"], r["end"])
        else:
            merged.append(r)

    return {"indexes": merged}
