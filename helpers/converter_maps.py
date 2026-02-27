from __future__ import annotations

import asyncio
import cutlet

import database

from helpers.fuzzy_matcher import preprocess
from pjsk_api.client import PJSKClient

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core import SbugaFastAPI

_katsu = cutlet.Cutlet()
_katsu_foreign = cutlet.Cutlet(ensure_ascii=False)

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


def _romaji(text: str) -> str | None:
    try:
        return _katsu.romaji(text).strip("?").lower().strip()
    except Exception:
        return None


def _romaji_foreign(text: str) -> str | None:
    try:
        return _katsu_foreign.romaji(text).strip("?").lower().strip()
    except Exception:
        return None


def _romanize_music(music: dict) -> list[str]:
    keys = []
    title = music["title"].strip()
    pronunciation = music.get("pronunciation", "")

    keys.append(preprocess(title))

    for text in [title, pronunciation]:
        if not text:
            continue
        for fn in [_romaji, _romaji_foreign]:
            r = fn(text)
            if r:
                keys.append(preprocess(r))

    return list(dict.fromkeys(keys))


def _romanize_event(event: dict) -> list[str]:
    keys = []
    title = event["name"].strip().lower()

    keys.append(preprocess(title))

    for fn in [_romaji, _romaji_foreign]:
        r = fn(title)
        if r:
            keys.append(preprocess(r))

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

    loop = asyncio.get_event_loop()

    jp_keys_list: list[list[str]] = await asyncio.gather(
        *[loop.run_in_executor(None, _romanize_music, m) for m in jp_musics]
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
        key = preprocess(alias)
        jp_diffs = jp_diff_map.get(music_id, frozenset())
        en_diffs = en_diff_map.get(music_id, frozenset())
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

    loop = asyncio.get_event_loop()

    jp_keys_list: list[list[str]] = await asyncio.gather(
        *[loop.run_in_executor(None, _romanize_event, e) for e in jp_events]
    )

    new_jp: dict[str, int] = {}
    new_en: dict[str, int] = {}

    # JP events
    for event, keys in zip(jp_events, jp_keys_list):
        event_id = event["id"]
        for key in keys:
            new_jp[key] = event_id
            if event_id in en_ids:
                new_en[key] = event_id

    # EN events
    for event in en_events:
        event_id = event["id"]
        for key in _plain_event_keys(event):
            new_en[key] = event_id
            if event_id in jp_ids:
                new_jp[key] = event_id

    # Aliases
    for alias, event_id in aliases.items():
        key = preprocess(alias)
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

    loop = asyncio.get_event_loop()
    new_map: dict[str, int] = {}

    async def _add_character(char_id: int, names: list[str]) -> None:
        for name in names:
            if not name:
                continue
            new_map[preprocess(name)] = char_id
            for fn in [_romaji, _romaji_foreign]:
                r = await loop.run_in_executor(None, fn, name)
                if r:
                    new_map[preprocess(r)] = char_id

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


# add/remove new aliases without rebuilding entire maps
def add_song_alias(
    alias: str,
    music_id: int,
    region: str | None = None,
) -> None:
    key = preprocess(alias)
    regions = [region] if region else list(_song_maps.keys())
    for r in regions:
        mapping = _song_maps.get(r, {})
        diffs = next(
            (v[1] for v in mapping.values() if v[0] == music_id),
            frozenset(),
        )
        mapping[key] = (music_id, diffs)


def add_event_alias(
    alias: str,
    event_id: int,
    region: str | None = None,
) -> None:
    key = preprocess(alias)
    regions = [region] if region else list(_event_maps.keys())
    for r in regions:
        mapping = _event_maps.get(r, {})
        mapping[key] = event_id


def remove_song_alias(
    alias: str,
    region: str | None = None,
) -> None:
    key = preprocess(alias)
    regions = [region] if region else list(_song_maps.keys())
    for r in regions:
        _song_maps.get(r, {}).pop(key, None)


def remove_event_alias(
    alias: str,
    region: str | None = None,
) -> None:
    key = preprocess(alias)
    regions = [region] if region else list(_event_maps.keys())
    for r in regions:
        _event_maps.get(r, {}).pop(key, None)
