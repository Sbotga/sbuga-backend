from database.query import ExecutableQuery


def remove_event_alias(id: int) -> ExecutableQuery:
    return ExecutableQuery(
        "DELETE FROM event_aliases WHERE id = $1",
        id,
    )


def remove_song_alias(id: int) -> ExecutableQuery:
    return ExecutableQuery(
        "DELETE FROM song_aliases WHERE id = $1",
        id,
    )
