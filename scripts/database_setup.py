import asyncio

import asyncpg
import yaml

with open("config.yml", "r") as f:
    config = yaml.load(f, yaml.Loader)

psql_config = config["psql"]


async def main():
    db = await asyncpg.create_pool(
        host=psql_config["host"],
        user=psql_config["user"],
        database=psql_config["database"],
        password=psql_config["password"],
        port=psql_config["port"],
        min_size=psql_config["pool-min-size"],
        max_size=psql_config["pool-max-size"],
        ssl="disable",
    )
    print("Connected!")
    # uncomment first block ONLY to delete all tables.
    # should not ever be run for production
    queries = [
        # """DO $$
        # DECLARE
        #     r RECORD;
        # BEGIN
        #     -- Iterate over each table and drop it
        #     FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
        #         EXECUTE 'DROP TABLE IF EXISTS public.' || r.tablename || ' CASCADE';
        #     END LOOP;
        # END $$;
        # """,
        """
        CREATE TABLE IF NOT EXISTS account (
            id BIGINT NOT NULL,
            display_name TEXT NOT NULL,
            username VARCHAR(255) NOT NULL UNIQUE,
            salted_password VARCHAR(255) NOT NULL,
            email TEXT NOT NULL,
            base_email TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
            banned BOOLEAN NOT NULL DEFAULT false,
            description TEXT NOT NULL DEFAULT 'This user hasn''t set a description!',
            profile_hash TEXT DEFAULT NULL,
            banner_hash TEXT DEFAULT NULL,
            valid_session_uuid TEXT NOT NULL DEFAULT gen_random_uuid()::TEXT,
            email_verified BOOLEAN NOT NULL DEFAULT FALSE,
            PRIMARY KEY (id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS song_aliases (
            id SERIAL PRIMARY KEY,
            alias TEXT NOT NULL UNIQUE,
            music_id INTEGER NOT NULL,
            region TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            created_by BIGINT REFERENCES account(id) ON DELETE SET NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS event_aliases (
            id SERIAL PRIMARY KEY,
            alias TEXT NOT NULL UNIQUE,
            event_id INTEGER NOT NULL,
            region TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            created_by BIGINT REFERENCES account(id) ON DELETE SET NULL
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS account_permissions (
            id SERIAL PRIMARY KEY,
            account_id BIGINT NOT NULL REFERENCES account(id) ON DELETE CASCADE,
            permission TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE (account_id, permission)
        );
        """,
        """
            CREATE INDEX IF NOT EXISTS idx_account_email ON account(email);
            CREATE INDEX IF NOT EXISTS idx_account_base_email ON account(base_email);
            CREATE INDEX IF NOT EXISTS idx_account_valid_session_uuid ON account(valid_session_uuid);
        """,
    ]
    async with db.acquire() as connection:
        for query in queries:
            try:
                await connection.execute(query)
            except asyncpg.exceptions.InsufficientPrivilegeError as e:
                print(f"Permission denied: {e}")
            except asyncpg.exceptions.PostgresSyntaxError:
                print(query)
                raise
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
