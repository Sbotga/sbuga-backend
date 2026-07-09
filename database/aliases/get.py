from database.models import EventAlias, SongAlias
from database.query import SelectQuery


def get_event_aliases() -> SelectQuery[EventAlias]:
    return SelectQuery(
        EventAlias,
        "SELECT * FROM event_aliases",
    )


def get_event_alias(id: int) -> SelectQuery[EventAlias]:
    return SelectQuery(
        EventAlias,
        "SELECT * FROM event_aliases WHERE id = $1",
        id,
    )


def get_song_aliases() -> SelectQuery[SongAlias]:
    return SelectQuery(
        SongAlias,
        "SELECT * FROM song_aliases",
    )


def get_song_alias(id: int) -> SelectQuery[SongAlias]:
    return SelectQuery(
        SongAlias,
        "SELECT * FROM song_aliases WHERE id = $1",
        id,
    )


def get_song_alias_by_alias(alias: str) -> SelectQuery[SongAlias]:
    """Aliases are unique across *every* song, so this finds whichever song holds it."""
    return SelectQuery(
        SongAlias,
        "SELECT * FROM song_aliases WHERE alias = $1",
        alias,
    )


def get_event_alias_by_alias(alias: str) -> SelectQuery[EventAlias]:
    """Aliases are unique across *every* event, so this finds whichever event holds it."""
    return SelectQuery(
        EventAlias,
        "SELECT * FROM event_aliases WHERE alias = $1",
        alias,
    )
