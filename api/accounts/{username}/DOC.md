## GET `/api/accounts/{username}`

Returns public profile information for an account.

### Response `200`
```json
{
  "user": {
    "id": 1234567890,
    "display_name": "Example",
    "username": "example",
    "created_at": 1700000000000,
    "updated_at": 1700000000000,
    "description": "This user hasn't set a description!",
    "profile_hash": "abc123...",
    "banner_hash": "abc123..."
  },
  "asset_base_url": "public bucket base url"
}
```

Timestamps are in **milliseconds since Unix epoch**. `profile_hash` and `banner_hash` may be `null` if not set.

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `404` | Account not found. | `account_not_found` |
```json
{
  "detail": "detail_code"
}
```