from __future__ import annotations

from rapidfuzz import fuzz, process as fuzz_process
from helpers.fuzzy_matcher import preprocess
from helpers.converter_maps import _song_maps, _character_map, _event_maps


def match_difficulty(query: str) -> str | None:
    diffs = {
        "append": "append",
        "master": "master",
        "expert": "expert",
        "hard": "hard",
        "normal": "normal",
        "easy": "easy",
        "apd": "append",
        "mas": "master",
        "exp": "expert",
        "ex": "expert",
        "norm": "normal",
        "ez": "easy",
    }
    return diffs.get(query.lower().strip())


def _fuzzy_match(
    query: str,
    mapping: dict,
    sensitivity: float,
    multi: bool,
) -> list:
    """Always returns a list. Caller decides whether to unwrap."""
    if not mapping:
        return []

    query = preprocess(query)
    keys = list(mapping.keys())

    results = fuzz_process.extract(
        query,
        keys,
        scorer=fuzz.WRatio,
        processor=None,
        limit=10,
        score_cutoff=sensitivity * 100,
    )

    seen: set = set()
    out = []
    for match_key, score, _ in results:
        val = mapping[match_key]
        uid = val[0] if isinstance(val, tuple) else val
        if uid not in seen:
            seen.add(uid)
            out.append(uid)

    return out


def _merge_maps(maps: list[dict]) -> dict:
    merged: dict[str, any] = {}
    seen_ids: set[int] = set()
    for mapping in maps:
        for key, val in mapping.items():
            uid = val[0] if isinstance(val, tuple) else val
            if uid not in seen_ids:
                merged[key] = val
                seen_ids.add(uid)
    return merged


def match_song(
    query: str,
    region: str | None = None,
    sensitivity: float = 0.5,
    multi: bool = False,
    difficulties: list[str] | None = None,
) -> int | None | list[int]:
    # get map
    if region:
        mapping = _song_maps.get(region, {})
    else:
        mapping = _merge_maps(list(_song_maps.values()))

    if not mapping:
        return [] if multi else None

    # direct id lookup
    if query.strip().isdigit():
        mid = int(query.strip())
        entry = next((v for v in mapping.values() if v[0] == mid), None)
        if entry:
            if difficulties and not all(d in entry[1] for d in difficulties):
                return [] if multi else None
            return [mid] if multi else mid

    # difficulty filter
    if difficulties:
        filtered = {
            k: v for k, v in mapping.items() if all(d in v[1] for d in difficulties)
        }
    else:
        filtered = mapping

    if not filtered:
        return [] if multi else None

    results = _fuzzy_match(query, filtered, sensitivity, multi=True)

    if not multi:
        return results[0] if results else None
    return results[:10]


def match_character(
    query: str,
    sensitivity: float = 0.6,
    multi: bool = False,
) -> int | None | list[int]:
    if not _character_map:
        return [] if multi else None

    if query.strip().isdigit():
        cid = int(query.strip())
        if cid in _character_map.values():
            return [cid] if multi else cid

    results = _fuzzy_match(query, _character_map, sensitivity, multi=True)

    if not multi:
        return results[0] if results else None
    return results[:10]


def match_event(
    query: str,
    region: str | None = None,
    sensitivity: float = 0.5,
    multi: bool = False,
) -> int | None | list[int]:
    if region:
        mapping = _event_maps.get(region, {})
    else:
        mapping = _merge_maps(list(_event_maps.values()))

    if not mapping:
        return [] if multi else None

    if query.strip().isdigit():
        eid = int(query.strip())
        if eid in mapping.values():
            return [eid] if multi else eid

    results = _fuzzy_match(query, mapping, sensitivity, multi=True)

    if not multi:
        return results[0] if results else None
    return results[:10]
