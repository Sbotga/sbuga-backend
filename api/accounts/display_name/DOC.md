## POST `/api/account/display_name`

Changes the display_name for the authenticated account.

### Authorization

| Header | Value |
|---|---|
| `Authorization` | Access token obtained from signin or signup. |

### Request Body

| Field | Type | Description |
|---|---|---|
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
| `404` | Account not found (shouldn't happen) | `account_not_found` |

```json
{
  "detail": "detail_code"
}
```