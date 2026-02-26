from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from typing import Literal
import asyncio
from pydantic import BaseModel

from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from helpers.converters import match_song

router = APIRouter()


class MusicSearchBody(BaseModel):
    query: str
    region: Literal["en", "jp"] | None = None
    difficulties: (
        list[Literal["easy", "normal", "hard", "expert", "master", "append"]] | None
    ) = None


def _build_music(
    music: dict,
    vocals: list,
    tags: list,
    original: dict | None,
    collaboration: dict | None,
    difficulties: list,
    asset_variants: list,
    artists: list,
    base_url: str,
    region: str,
    image_type: Literal["webp", "png"],
) -> dict:
    music_id = music["id"]

    music_tags = [t["musicTag"] for t in tags if t["musicId"] == music_id]
    original_video = original["videoLink"] if original else None
    collab_label = collaboration["label"] if collaboration else None
    artist = next((a for a in artists if a["id"] == music.get("creatorArtistId")), None)

    music_difficulties = [
        {
            "difficulty": d["musicDifficulty"],
            "play_level": d["playLevel"],
            "total_note_count": d["totalNoteCount"],
        }
        for d in difficulties
        if d["musicId"] == music_id
    ]

    ab_name = music["assetbundleName"]
    jacket_url = f"{base_url}/api/pjsk_data/assets/music/jacket/{ab_name}/{ab_name}.{image_type}?region={region}"

    music_vocals = []
    for vocal in vocals:
        if vocal["musicId"] != music_id:
            continue
        variants = [
            {
                "id": v["id"],
                "seq": v["seq"],
                "asset_type": v["musicAssetType"],
                "assetbundle_name": v["assetbundleName"],
            }
            for v in asset_variants
            if v["musicVocalId"] == vocal["id"]
        ]
        music_vocals.append(
            {
                "id": vocal["id"],
                "vocal_type": vocal["musicVocalType"],
                "caption": vocal["caption"],
                "characters": [
                    {
                        "character_type": c["characterType"],
                        "character_id": c["characterId"],
                        "seq": c["seq"],
                    }
                    for c in vocal["characters"]
                ],
                "assetbundle_name": vocal["assetbundleName"],
                "published_at": vocal.get("archivePublishedAt"),
                "variants": variants,
            }
        )

    return {
        "id": music_id,
        "title": music["title"],
        "pronunciation": music.get("pronunciation"),
        "lyricist": music.get("lyricist"),
        "composer": music.get("composer"),
        "arranger": music.get("arranger"),
        "artist": (
            {
                "id": artist["id"],
                "name": artist["name"],
                "pronunciation": artist.get("pronunciation"),
            }
            if artist
            else None
        ),
        "categories": music.get("categories", []),
        "tags": music_tags,
        "published_at": music.get("publishedAt"),
        "released_at": music.get("releasedAt"),
        "is_newly_written": music.get("isNewlyWrittenMusic"),
        "is_full_length": music.get("isFullLength"),
        "filler_sec": music.get("fillerSec"),
        "jacket_url": jacket_url,
        "collaboration": collab_label,
        "original_video": original_video,
        "difficulties": music_difficulties,
        "vocals": music_vocals,
    }


def _build_music_simple(
    music: dict,
    difficulties: list,
    base_url: str,
    region: str,
    image_type: Literal["webp", "png"],
) -> dict:
    music_id = music["id"]
    ab_name = music["assetbundleName"]
    jacket_url = f"{base_url}/api/pjsk_data/assets/music/jacket/{ab_name}/{ab_name}.{image_type}?region={region}"

    return {
        "id": music_id,
        "title": music["title"],
        "difficulties": [
            d["musicDifficulty"] for d in difficulties if d["musicId"] == music_id
        ],
        "jacket_url": jacket_url,
    }


@router.get(
    "/simple",
    summary="Get musics (simple)",
    description="Returns a simplified list of all musics for a given region, including only ID, title, difficulties, and jacket URL.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "musics": [
                            {
                                "id": 1,
                                "title": "Tell Your World",
                                "difficulties": [
                                    "easy",
                                    "normal",
                                    "hard",
                                    "expert",
                                    "master",
                                ],
                                "jacket_url": "https://sbuga.com/api/pjsk_data/assets/music/jacket/jacket_s_001/jacket_s_001.webp?region=en",
                            }
                        ]
                    }
                }
            },
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def get_musics_simple(
    request: Request,
    region: Literal["en", "jp"],
    image_type: Literal["webp", "png"] = "webp",
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    musics, difficulties = await asyncio.gather(
        client.get_master("musics"),
        client.get_master("musicDifficulties"),
    )

    result = [
        _build_music_simple(
            music=music,
            difficulties=difficulties,
            base_url=app.base_url,
            region=region,
            image_type=image_type,
        )
        for music in musics
    ]

    return {"musics": result}


@router.get(
    "",
    summary="Get musics",
    description="Returns a compiled list of all musics for a given region, including vocals, difficulties, tags, collaboration, and original video.",
    responses={
        200: {
            "description": "Success",
            "content": {
                "application/json": {
                    "example": {
                        "musics": [
                            {
                                "id": 1,
                                "title": "Tell Your World",
                                "pronunciation": "てるゆあわーるど",
                                "lyricist": "kz",
                                "composer": "kz",
                                "arranger": "kz",
                                "artist": {
                                    "id": 1,
                                    "name": "livetune",
                                    "pronunciation": "らいぶちゅーん",
                                },
                                "categories": ["mv"],
                                "tags": ["all"],
                                "published_at": 1560148031000,
                                "released_at": 1326812400000,
                                "is_newly_written": False,
                                "is_full_length": False,
                                "filler_sec": 9.0,
                                "jacket_url": "https://sbuga.com/api/pjsk_data/assets/music/jacket/jacket_s_001/jacket_s_001.png?region=en",
                                "collaboration": None,
                                "original_video": "https://youtu.be/PqJNc9KVIZE",
                                "difficulties": [
                                    {
                                        "difficulty": "easy",
                                        "play_level": 5,
                                        "total_note_count": 220,
                                    }
                                ],
                                "vocals": [
                                    {
                                        "id": 1,
                                        "vocal_type": "original_song",
                                        "caption": "バーチャル・シンガーver.",
                                        "characters": [
                                            {
                                                "character_type": "game_character",
                                                "character_id": 21,
                                                "seq": 10,
                                            }
                                        ],
                                        "assetbundle_name": "0001_01",
                                        "published_at": 1233284400000,
                                        "variants": [],
                                    }
                                ],
                            }
                        ]
                    }
                }
            },
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def get_musics(
    request: Request,
    region: Literal["en", "jp"],
    image_type: Literal["webp", "png"] = "webp",
):
    app: SbugaFastAPI = request.app

    client = app.pjsk_clients.get(region)
    if not client:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    (
        musics,
        vocals,
        tags,
        originals,
        collaborations,
        difficulties,
        asset_variants,
        artists,
    ) = await asyncio.gather(
        client.get_master("musics"),
        client.get_master("musicVocals"),
        client.get_master("musicTags"),
        client.get_master("musicOriginals"),
        client.get_master("musicCollaborations"),
        client.get_master("musicDifficulties"),
        client.get_master("musicAssetVariants"),
        client.get_master("musicArtists"),
    )

    originals_by_music = {o["musicId"]: o for o in originals}
    collaborations_by_id = {c["id"]: c for c in collaborations}

    result = [
        _build_music(
            music=music,
            vocals=vocals,
            tags=tags,
            original=originals_by_music.get(music["id"]),
            collaboration=collaborations_by_id.get(music.get("musicCollaborationId")),
            difficulties=difficulties,
            asset_variants=asset_variants,
            artists=artists,
            base_url=app.base_url,
            region=region,
            image_type=image_type,
        )
        for music in musics
    ]

    return {"musics": result}


@router.post(
    "/search",
    summary="Search musics",
    description=(
        "Fuzzy search musics by title. Returns a list of matching music IDs sorted by relevance (closest first). "
        "`region` is optional — if omitted, searches across all regions. "
        "`difficulties` optionally filters to only songs that have ALL specified difficulties."
    ),
    responses={
        200: {
            "description": "Success",
            "content": {"application/json": {"example": {"ids": [1, 5, 23]}}},
        },
        503: COMMON_RESPONSES[503],
    },
    tags=["PJSK Data"],
)
async def search_musics(
    request: Request,
    body: MusicSearchBody,
):
    app: SbugaFastAPI = request.app

    if body.region and not app.pjsk_clients.get(body.region):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ErrorDetailCode.PJSKClientUnavailable.value,
        )

    results = match_song(
        query=body.query,
        region=body.region,
        multi=True,
        difficulties=body.difficulties,
    )

    return {"ids": results}
