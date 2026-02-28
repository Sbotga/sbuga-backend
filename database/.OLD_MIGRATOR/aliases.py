# MIGRATED ON 2026-02-27 8:04 EST

import asyncpg
import asyncio
import json

OLD_DB = "postgresql://user:password@localhost/old_db"
NEW_DB = "postgresql://user:password@localhost/new_db"


async def migrate():
    old_conn = await asyncpg.connect(OLD_DB)
    new_conn = await asyncpg.connect(NEW_DB)

    try:
        row = await old_conn.fetchrow("SELECT aliases FROM song_aliases LIMIT 1")
        data: dict = json.loads(row["aliases"])

        inserts = []
        for music_id_str, entry in data.items():
            music_id = int(music_id_str)
            for alias in entry["aliases"]:
                inserts.append((alias, music_id))

        await new_conn.executemany(
            """
            INSERT INTO song_aliases (alias, music_id)
            VALUES ($1, $2)
            ON CONFLICT (alias) DO NOTHING
            """,
            inserts,
        )

        print(f"Inserted {len(inserts)} aliases")
    finally:
        await old_conn.close()
        await new_conn.close()


asyncio.run(migrate())
