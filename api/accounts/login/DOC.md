## POST `/api/login`

Signs into an existing account.

### Request Body

| Field | Type | Description |
|---|---|---|
| `username` | string | The account username. |
| `password` | string | The account password. |
| `turnstile_response` | string | Cloudflare Turnstile token from the client-side widget. |

### Response
```json
{
  "user": {user data},
  "access_token": "access authorization token",
  "refresh_token": "refresh authorization token",
  "asset_base_url": "public bucket asset base url"
}
```

Timestamps are in **milliseconds since Unix epoch**.

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Invalid turnstile response. | `turnstile_invalid` |
| `401` | Invalid username or password. | `invalid_login` |
```json
{
  "detail": "detail_code"
}
```