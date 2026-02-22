## POST `/api/account/password`

Changes the password for the authenticated account.

### Request Body

| Field | Type | Description |
|---|---|---|
| `old_password` | string | The current password. |
| `new_password` | string | The new password. Must pass password validation. |

### Response `200`

Password changed successfully. Empty response body.

```json
{}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Invalid new password. | `password_invalid` |
| `401` | Old password is incorrect. | `invalid_login` |

```json
{
  "detail": "detail_code"
}
```