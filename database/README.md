# Raw SQL with models
Query generators that aren't SQL-injectable, using asyncpg.

These can be used by running something like:
```py
query = create_query(...)
async with app.acquire_db() as conn:
    # see usage for each query below
```

Here are the current 2 types of queries:

### SelectQuery
Returns.
```py
def create_query(input_model_or_args) -> SelectQuery[PydanticModel_1]:
    # Build your query using args!
    return SelectQuery(
        PydanticModel_1,
        """
        SELECT * FROM users WHERE id = $1;
        """,
        id # args here
    )
```

Usage:
```py
query = create_query(...)
async with app.acquire_db() as conn:
    result: PydanticModel_1 = await conn.fetchrow(query) # fetch a single row (if your query returns multiple, gets the first one), returns None if no rows found
    result: List[PydanticModel_1] = await conn.fetch(query) # fetch multiple rows, returns [] if no rows found
```

### ExecutableQuery
No return.
```py
def create_query(
    input_model_or_args
) -> ExecutableQuery:
    # Build your query using args!
    return ExecutableQuery(
        """
        INSERT INTO some_table (a, b, c)
        VALUES ($1, $2, $3)
        """,
        a, # arg 1
        b, # arg 2
        c # arg 3
    )
```

Usage:
```py
query = create_query(...)
async with app.acquire_db() as conn:
    await conn.execute(query) # returns None
```