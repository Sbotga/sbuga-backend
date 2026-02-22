## POST `/api/account/display_name`

Changes the display_name for the authenticated account.

### Request Body

| Field | Type | Description |
|---|---|---|
| `password` | string | The current password. |
| `new_display_name` | string | The new display name. |

### Response `200`

Username changed successfully.

```json
{
  "display_name": "new display name"
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Invalid new display name. | `display_name_invalid` |
| `401` | Old password is incorrect. | `invalid_login` |

```json
{
  "detail": "detail_code"
}
```