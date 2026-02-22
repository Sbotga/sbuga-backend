## POST `/api/account/username`

Changes the username for the authenticated account.

### Request Body

| Field | Type | Description |
|---|---|---|
| `password` | string | The current password. |
| `new_username` | string | The new username. |

### Response `200`

Username changed successfully.

```json
{
  "username": "new username"
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Invalid new username. | `username_invalid` |
| `401` | Old password is incorrect. | `invalid_login` |

```json
{
  "detail": "detail_code"
}
```