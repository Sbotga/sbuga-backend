from fastapi import APIRouter, Request, HTTPException, status
from core import SbugaFastAPI
from typing import Literal
import asyncio
from pydantic import BaseModel

from helpers.erroring import ErrorDetailCode, ERROR_RESPONSE, COMMON_RESPONSES
from helpers.converters import match_song
from helpers.converter_maps import _song_maps

router = APIRouter()

# tw/kr assets are not extracted/uploaded (subset of jp, same bundle names) —
# their asset URLs point at the jp tree instead.
ASSET_REGION = {"tw": "jp", "kr": "jp"}


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
    game_characters: dict,
    outside_characters: dict,
    asset_base_url: str,
    region: str,
    image_type: Literal["webp", "png"],
) -> dict:
    music_id = music["id"]
    map_region = region
    region = ASSET_REGION.get(region, region)

    music_tags = [t["musicTag"] for t in tags if t["musicId"] == music_id]
    # nuverse (tw/kr) masterdata wraps categories: [{"musicCategoryName": "mv"}]
    categories = [
        c["musicCategoryName"] if isinstance(c, dict) else c
        for c in music.get("categories", [])
    ]
    original_video = original["videoLink"] if original else None
    collab_label = collaboration["label"] if collaboration else None
    collab_id = collaboration["id"] if collaboration else None
    artist = next((a for a in artists if a["id"] == music.get("creatorArtistId")), None)

    padded_id = f"{music_id:04d}"
    music_difficulties = [
        {
            "difficulty": d["musicDifficulty"],
            "play_level": d["playLevel"],
            "total_note_count": d["totalNoteCount"],
            "chart_url": f"{asset_base_url}/pjsk_data/{region}/music/music_score/{padded_id}_01/{d['musicDifficulty']}.txt",
        }
        for d in difficulties
        if d["musicId"] == music_id
    ]

    ab_name = music["assetbundleName"]
    jacket_url = f"{asset_base_url}/pjsk_data/{region}/music/jacket/{ab_name}/{ab_name}.{image_type}"
    background_v1_url = (
        f"{asset_base_url}/pjsk_data/{region}/music/jacket/{ab_name}/{ab_name}_v1.png"
    )
    background_v3_url = (
        f"{asset_base_url}/pjsk_data/{region}/music/jacket/{ab_name}/{ab_name}_v3.png"
    )

    music_vocals = []
    for vocal in vocals:
        if vocal["musicId"] != music_id:
            continue
        variants = []
        for v in asset_variants:
            if v["musicVocalId"] != vocal["id"]:
                continue
            vd = {
                "id": v["id"],
                "seq": v["seq"],
                "asset_type": v["musicAssetType"],
                "assetbundle_name": v["assetbundleName"],
            }
            if v["musicAssetType"] == "jacket":
                vab = v["assetbundleName"]
                vd["jacket_url"] = (
                    f"{asset_base_url}/pjsk_data/{region}/music/jacket/{ab_name}/{vab}.{image_type}"
                )
                vd["background_v1_url"] = (
                    f"{asset_base_url}/pjsk_data/{region}/music/jacket/{ab_name}/{vab}_v1.png"
                )
                vd["background_v3_url"] = (
                    f"{asset_base_url}/pjsk_data/{region}/music/jacket/{ab_name}/{vab}_v3.png"
                )
            variants.append(vd)

        vab_name = vocal["assetbundleName"]
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
                "assetbundle_name": vab_name,
                "bgm_url": f"{asset_base_url}/pjsk_data/{region}/music/long/{vab_name}/{vab_name}.mp3",
                "bgm_nosil_url": f"{asset_base_url}/pjsk_data/{region}/music/long/{vab_name}/{vab_name}_silence_removed.mp3",
                "preview_url": f"{asset_base_url}/pjsk_data/{region}/music/short/{vab_name}/{vab_name}_short.mp3",
                "published_at": vocal.get("archivePublishedAt"),
                "variants": variants,
            }
        )

    region_map = _song_maps.get(map_region, {})
    title_variants = list(
        dict.fromkeys(key for key, (mid, _) in region_map.items() if mid == music_id)
    )

    used_game_ids = set()
    used_outside_ids = set()
    for v in music_vocals:
        for c in v["characters"]:
            if c["character_type"] == "game_character":
                used_game_ids.add(c["character_id"])
            else:
                used_outside_ids.add(c["character_id"])

    return {
        "id": music_id,
        "title": music["title"],
        "pronunciation": music.get("pronunciation"),
        "title_variants": title_variants,
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
        "categories": categories,
        "tags": music_tags,
        "published_at": music.get("publishedAt"),
        "released_at": music.get("releasedAt"),
        "removed_at": music.get("removedAt"),
        "is_newly_written": music.get("isNewlyWrittenMusic"),
        "is_full_length": music.get("isFullLength"),
        "filler_sec": music.get("fillerSec"),
        "sec_for_music_score_maker": music.get("secForMusicScoreMaker"),
        "jacket_url": jacket_url,
        "background_v1_url": background_v1_url,
        "background_v3_url": background_v3_url,
        "collaboration": collab_label,
        "collaboration_id": collab_id,
        "original_video": original_video,
        "difficulties": music_difficulties,
        "vocals": music_vocals,
        "game_characters": {
            cid: game_characters[cid] for cid in used_game_ids if cid in game_characters
        },
        "outside_characters": {
            cid: outside_characters[cid]
            for cid in used_outside_ids
            if cid in outside_characters
        },
    }


def _build_music_simple(
    music: dict,
    difficulties: list,
    asset_base_url: str,
    region: str,
    image_type: Literal["webp", "png"],
) -> tuple[dict, int]:
    music_id = music["id"]
    ab_name = music["assetbundleName"]
    region = ASSET_REGION.get(region, region)
    jacket_url = f"{asset_base_url}/pjsk_data/{region}/music/jacket/{ab_name}/{ab_name}.{image_type}"

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
    region: Literal["en", "jp", "tw", "kr"],
    image_type: Literal["webp", "png"] = "webp",
    ignore_leak: bool = False,
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
            asset_base_url=app.s3_asset_base_url,
            region=region,
            image_type=image_type,
        )
        for music in musics
        if ignore_leak or not app.check_leak(music["publishedAt"])
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
                                        "chart_url": "https://sbugaisthemostsbuga.sbuga.com/pjsk_data/en/music/music_score/0001_01/easy.txt",
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
                                        "bgm_url": "https://sbugaisthemostsbuga.sbuga.com/pjsk_data/en/music/long/0001_01/0001_01.mp3",
                                        "preview_url": "https://sbugaisthemostsbuga.sbuga.com/pjsk_data/en/music/short/0001_01/0001_01_short.mp3",
                                        "published_at": 1233284400000,
                                        "variants": [
                                            {
                                                "id": 42,
                                                "seq": 1,
                                                "asset_type": "jacket",
                                                "assetbundle_name": "jacket_s_001_v2",
                                                "jacket_url": "https://sbugaisthemostsbuga.sbuga.com/pjsk_data/en/music/jacket/jacket_s_001_v2/jacket_s_001_v2.png",
                                            }
                                        ],
                                    }
                                ],
                                "game_characters": {
                                    "21": {
                                        "givenName": "Miku",
                                        "firstName": "Hatsune",
                                        "unit": "piapro",
                                    }
                                },
                                "outside_characters": {},
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
    region: Literal["en", "jp", "tw", "kr"],
    image_type: Literal["webp", "png"] = "webp",
    ignore_leak: bool = False,
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
        game_chars_raw,
        outside_chars_raw,
    ) = await asyncio.gather(
        client.get_master("musics"),
        client.get_master("musicVocals"),
        client.get_master("musicTags"),
        client.get_master("musicOriginals"),
        client.get_master("musicCollaborations"),
        client.get_master("musicDifficulties"),
        client.get_master("musicAssetVariants"),
        client.get_master("musicArtists"),
        client.get_master("gameCharacters"),
        client.get_master("outsideCharacters"),
    )

    game_characters = {
        c["id"]: {
            "givenName": c.get("givenName", ""),
            "firstName": c.get("firstName", ""),
            "unit": c.get("unit", ""),
        }
        for c in game_chars_raw
    }
    outside_characters = {c["id"]: {"name": c["name"]} for c in outside_chars_raw}

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
            game_characters=game_characters,
            outside_characters=outside_characters,
            asset_base_url=app.s3_asset_base_url,
            region=region,
            image_type=image_type,
        )
        for music in musics
        if ignore_leak or not app.check_leak(music["publishedAt"])
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

    if app.config.pjsk.hide_leaks:
        if body.region:
            client = app.pjsk_clients[body.region]
            musics = await client.get_master("musics")
            result_set = set(results)
            publish_map = {
                music["id"]: music["publishedAt"]
                for music in musics
                if music["id"] in result_set
            }
            filtered = [
                mid
                for mid in results
                if mid not in publish_map or not app.check_leak(publish_map[mid])
            ]
        else:
            result_set = set(results)
            leaked = set(result_set)
            for region, client in app.pjsk_clients.items():
                musics = await client.get_master("musics")
                not_leaked_in_region = {
                    music["id"]
                    for music in musics
                    if music["id"] in result_set
                    and not app.check_leak(music["publishedAt"])
                }
                leaked -= not_leaked_in_region
            filtered = [mid for mid in results if mid not in leaked]
    else:
        filtered = results
    return {"ids": filtered}
