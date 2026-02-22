## POST `/accounts/session/refresh`

Exchanges a refresh token for a new access token.

### Headers

| Header | Value |
|---|---|
| `Authorization` | Refresh token. |

### Response `200`
```json
{
  "token": "eyJ..."
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `401` | Not logged in. | `not_logged_in` |
| `401` | Invalid or wrong token type. | `session_invalid` |
| `401` | Token expired. | `session_expired` |
| `403` | User banned. | `banned` |

```json
{
  "detail": "detail code"
}
```