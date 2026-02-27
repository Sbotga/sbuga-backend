from database.query import SelectQuery
from database.models import EventAlias, SongAlias


def add_event_alias(
    alias: str,
    event_id: int,
    region: str | None = None,
    created_by: int | None = None,
) -> SelectQuery[EventAlias]:
    return SelectQuery(
        EventAlias,
        """
        INSERT INTO event_aliases (alias, event_id, region, created_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (alias) DO NOTHING
        RETURNING *
        """,
        alias,
        event_id,
        region,
        created_by,
    )


def add_song_alias(
    alias: str,
    music_id: int,
    region: str | None = None,
    created_by: int | None = None,
) -> SelectQuery[SongAlias]:
    return SelectQuery(
        SongAlias,
        """
        INSERT INTO song_aliases (alias, music_id, region, created_by)
        VALUES ($1, $2, $3, $4)
        ON CONFLICT (alias) DO NOTHING
        RETURNING *
        """,
        alias,
        music_id,
        region,
        created_by,
    )
