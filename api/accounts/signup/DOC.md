# API Documentation

## POST `/api/signup`

Creates a new account.

### Request Body

| Field | Type | Description |
|---|---|---|
| `username` | string | The desired username. Must pass username validation. |
| `password` | string | The desired password. Must pass password validation. |
| `turnstile_response` | string | Cloudflare Turnstile token from the client-side widget. |

### Response

```json
{
  "id": 1234567890,
  "username": "example",
  "display_name": "Example",
  "created_at": 1700000000000,
  "updated_at": 1700000000000,
  "access_token": "access authorization token",
  "refresh_token": "refresh authorization token"
}
```

Timestamps are in **milliseconds since Unix epoch**.

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Invalid turnstile response. | turnstile_invalid |
| `400` | Invalid username. | username_invalid |
| `400` | Invalid password. | password_invalid |
| `400` | Invalid display name. | display_name_invalid |
| `409` | Username is already taken. | username_taken |
| `500` | Internal error (e.g. rare account ID collision) | internal_server_error |

```json
{
  "detail": "detail_code"
}
```