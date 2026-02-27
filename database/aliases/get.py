from database.models import EventAlias, SongAlias
from database.query import SelectQuery


def get_event_aliases() -> SelectQuery[EventAlias]:
    return SelectQuery(
        EventAlias,
        "SELECT * FROM event_aliases",
    )


def get_event_alias(alias: str) -> SelectQuery[EventAlias]:
    return SelectQuery(
        EventAlias,
        "SELECT * FROM event_aliases WHERE alias = $1",
        alias,
    )


def get_song_aliases() -> SelectQuery[SongAlias]:
    return SelectQuery(
        SongAlias,
        "SELECT * FROM song_aliases",
    )


def get_song_alias(alias: str) -> SelectQuery[SongAlias]:
    return SelectQuery(
        SongAlias,
        "SELECT * FROM song_aliases WHERE alias = $1",
        alias,
    )
