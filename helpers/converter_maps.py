from __future__ import annotations

import asyncio
import cutlet

import database

from helpers.fuzzy_matcher import preprocess
from pjsk_api.client import PJSKClient

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core import SbugaFastAPI

_katsu_hepburn = cutlet.Cutlet(
    system="hepburn", use_foreign_spelling=False, ensure_ascii=False
)
_katsu_nihon = cutlet.Cutlet(
    system="nihon", use_foreign_spelling=False, ensure_ascii=False
)
_katsu_kunrei = cutlet.Cutlet(
    system="kunrei", use_foreign_spelling=False, ensure_ascii=False
)

ROMANIZERS = [
    lambda text: _katsu_hepburn.romaji(text).lower().strip(),
    lambda text: _katsu_nihon.romaji(text).lower().strip(),
    lambda text: _katsu_kunrei.romaji(text).lower().strip(),
]

_song_maps: dict[str, dict[str, tuple[int, frozenset[str]]]] = {"jp": {}, "en": {}}
_character_map: dict[str, int] = {}
_event_maps: dict[str, dict[str, int]] = {"jp": {}, "en": {}}

_build_lock = asyncio.Lock()


async def get_song_aliases(app: SbugaFastAPI) -> dict[str, int]:
    async with app.acquire_db() as conn:
        rows: list[database.models.SongAlias] = await conn.fetch(
            database.aliases.get_song_aliases()
        )
    return {row.alias: row.music_id for row in rows}


async def get_event_aliases(app: SbugaFastAPI) -> dict[str, int]:
    async with app.acquire_db() as conn:
        rows: list[database.models.EventAlias] = await conn.fetch(
            database.aliases.get_event_aliases()
        )
    return {row.alias: row.event_id for row in rows}


def _is_romanized(original: str, result: str) -> bool:
    original_clean = "".join(preprocess(original).split())
    result_clean = "".join(preprocess(result).split())
    return result_clean != original_clean


def _romanize_text(text: str) -> list[str]:
    keys = []
    for fn in ROMANIZERS:
        try:
            r = fn(text)
        except Exception:
            continue
        if r and _is_romanized(text, r):
            keys.append(preprocess(r))
    return list(dict.fromkeys(keys))


def _romanize_music(music: dict) -> list[str]:
    keys = []
    title = music["title"].strip()
    pronunciation = music.get("pronunciation", "")

    keys.append(preprocess(title))

    for text in [title, pronunciation]:
        if not text:
            continue
        keys.extend(_romanize_text(text))

    return list(dict.fromkeys(keys))


def _romanize_event(event: dict) -> list[str]:
    keys = []
    title = event["name"].strip().lower()

    keys.append(preprocess(title))
    keys.extend(_romanize_text(title))

    short = event["assetbundleName"].split("_")[1]
    keys.append(preprocess(short))
    keys.append(preprocess(str(event["id"])))

    return list(dict.fromkeys(keys))


def _plain_event_keys(event: dict) -> list[str]:
    keys = [
        preprocess(event["name"].strip().lower()),
        preprocess(event["assetbundleName"].split("_")[1]),
        preprocess(str(event["id"])),
    ]
    return list(dict.fromkeys(keys))


def _romanize_alias(alias: str) -> list[str]:
    keys = [preprocess(alias)]
    keys.extend(_romanize_text(alias))
    return list(dict.fromkeys(keys))


async def _build_song_maps(
    jp_client: PJSKClient, en_client: PJSKClient, app: SbugaFastAPI
) -> None:
    jp_musics, en_musics, jp_difficulties, en_difficulties, aliases = (
        await asyncio.gather(
            jp_client.get_master("musics"),
            en_client.get_master("musics"),
            jp_client.get_master("musicDifficulties"),
            en_client.get_master("musicDifficulties"),
            get_song_aliases(app),
        )
    )

    jp_ids = {m["id"] for m in jp_musics}
    en_ids = {m["id"] for m in en_musics}

    def _diff_map(difficulties: list) -> dict[int, frozenset[str]]:
        result: dict[int, set[str]] = {}
        for d in difficulties:
            result.setdefault(d["musicId"], set()).add(d["musicDifficulty"])
        return {k: frozenset(v) for k, v in result.items()}

    jp_diff_map = _diff_map(jp_difficulties)
    en_diff_map = _diff_map(en_difficulties)

    jp_keys_list: list[list[str]] = await asyncio.gather(
        *[asyncio.to_thread(None, _romanize_music, m) for m in jp_musics]
    )

    new_jp: dict[str, tuple[int, frozenset[str]]] = {}
    new_en: dict[str, tuple[int, frozenset[str]]] = {}

    for music, keys in zip(jp_musics, jp_keys_list):
        music_id = music["id"]
        jp_diffs = jp_diff_map.get(music_id, frozenset())
        en_diffs = en_diff_map.get(music_id, frozenset())
        for key in keys:
            new_jp[key] = (music_id, jp_diffs)
            if music_id in en_ids:
                new_en[key] = (music_id, en_diffs)

    for music in en_musics:
        music_id = music["id"]
        key = preprocess(music["title"].strip())
        en_diffs = en_diff_map.get(music_id, frozenset())
        jp_diffs = jp_diff_map.get(music_id, frozenset())
        new_en[key] = (music_id, en_diffs)
        if music_id in jp_ids:
            new_jp[key] = (music_id, jp_diffs)

    for alias, music_id in aliases.items():
        jp_diffs = jp_diff_map.get(music_id, frozenset())
        en_diffs = en_diff_map.get(music_id, frozenset())
        for key in _romanize_alias(alias):
            if music_id in jp_ids:
                new_jp[key] = (music_id, jp_diffs)
            if music_id in en_ids:
                new_en[key] = (music_id, en_diffs)

    _song_maps["jp"] = new_jp
    _song_maps["en"] = new_en


async def _build_event_map(jp_client: PJSKClient, en_client: PJSKClient, app) -> None:
    jp_events, en_events, aliases = await asyncio.gather(
        jp_client.get_master("events"),
        en_client.get_master("events"),
        get_event_aliases(app),
    )

    jp_ids = {e["id"] for e in jp_events}
    en_ids = {e["id"] for e in en_events}

    jp_keys_list: list[list[str]] = await asyncio.gather(
        *[asyncio.to_thread(None, _romanize_event, e) for e in jp_events]
    )

    new_jp: dict[str, int] = {}
    new_en: dict[str, int] = {}

    for event, keys in zip(jp_events, jp_keys_list):
        event_id = event["id"]
        for key in keys:
            new_jp[key] = event_id
            if event_id in en_ids:
                new_en[key] = event_id

    for event in en_events:
        event_id = event["id"]
        for key in _plain_event_keys(event):
            new_en[key] = event_id
            if event_id in jp_ids:
                new_jp[key] = event_id

    for alias, event_id in aliases.items():
        for key in _romanize_alias(alias):
            if event_id in jp_ids:
                new_jp[key] = event_id
            if event_id in en_ids:
                new_en[key] = event_id

    _event_maps["jp"] = new_jp
    _event_maps["en"] = new_en


async def _build_character_map(jp_client: PJSKClient) -> None:
    game_characters, outside_characters = await asyncio.gather(
        jp_client.get_master("gameCharacters"),
        jp_client.get_master("outsideCharacters"),
    )

    new_map: dict[str, int] = {}

    async def _add_character(char_id: int, names: list[str]) -> None:
        for name in names:
            if not name:
                continue
            new_map[preprocess(name)] = char_id
            for key in await asyncio.to_thread(_romanize_text, name):
                new_map[key] = char_id

    tasks = []
    for char in game_characters:
        char_id = char["id"]
        given = char.get("givenName", "")
        first = char.get("firstName", "")

        names = []
        if given:
            names.append(given)
        if first:
            names.append(first)
        if given and first:
            names.append(f"{given}{first}")
            names.append(f"{first}{given}")

        tasks.append(_add_character(char_id, names))

    for char in outside_characters:
        char_id = char["id"]
        name = char.get("name", "")
        if name:
            tasks.append(_add_character(char_id, [name]))

    await asyncio.gather(*tasks)
    _character_map.update(new_map)


async def rebuild_maps(
    jp_client: PJSKClient, en_client: PJSKClient, app: SbugaFastAPI
) -> None:
    async with _build_lock:
        await asyncio.gather(
            _build_song_maps(jp_client, en_client, app),
            _build_event_map(jp_client, en_client, app),
            _build_character_map(jp_client),
        )


def add_song_alias(
    alias: str,
    music_id: int,
    region: str | None = None,
) -> None:
    regions = [region] if region else list(_song_maps.keys())
    for r in regions:
        mapping = _song_maps.get(r, {})
        diffs = next(
            (v[1] for v in mapping.values() if v[0] == music_id),
            frozenset(),
        )
        for key in _romanize_alias(alias):
            mapping[key] = (music_id, diffs)


def add_event_alias(
    alias: str,
    event_id: int,
    region: str | None = None,
) -> None:
    regions = [region] if region else list(_event_maps.keys())
    for r in regions:
        mapping = _event_maps.get(r, {})
        for key in _romanize_alias(alias):
            mapping[key] = event_id


def remove_song_alias(
    alias: str,
    region: str | None = None,
) -> None:
    regions = [region] if region else list(_song_maps.keys())
    for r in regions:
        mapping = _song_maps.get(r, {})
        for key in _romanize_alias(alias):
            mapping.pop(key, None)


def remove_event_alias(
    alias: str,
    region: str | None = None,
) -> None:
    regions = [region] if region else list(_event_maps.keys())
    for r in regions:
        mapping = _event_maps.get(r, {})
        for key in _romanize_alias(alias):
            mapping.pop(key, None)
