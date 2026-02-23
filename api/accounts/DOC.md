## GET `/api/account/me`

Returns the authenticated account's full profile information.

### Authorization

| Header | Value |
|---|---|
| `Authorization` | Access token obtained from signin or signup. |

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
    "banner_hash": "abc123...",
    "banned": false
  },
  "asset_base_url": "public bucket base url"
}
```

Timestamps are in **milliseconds since Unix epoch**. `profile_hash` and `banner_hash` may be `null` if not set.

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `401` | Not logged in. | `not_logged_in` |
| `401` | Token expired. | `session_expired` |
| `401` | Invalid token. | `session_invalid` |
```json
{
  "detail": "detail_code"
}
```

---

## DELETE `/api/account/profile`

Deletes the authenticated account's profile picture.

### Authorization

| Header | Value |
|---|---|
| `Authorization` | Access token obtained from signin or signup. |

### Response `200`
```json
{
  "result": "success"
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `401` | Not logged in. | `not_logged_in` |
| `401` | Token expired. | `session_expired` |
| `401` | Invalid token. | `session_invalid` |
```json
{
  "detail": "detail_code"
}
```

---

## DELETE `/api/account/banner`

Deletes the authenticated account's banner.

### Authorization

| Header | Value |
|---|---|
| `Authorization` | Access token obtained from signin or signup. |

### Response `200`
```json
{
  "result": "success"
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `401` | Not logged in. | `not_logged_in` |
| `401` | Token expired. | `session_expired` |
| `401` | Invalid token. | `session_invalid` |
```json
{
  "detail": "detail_code"
}
```

---

## POST `/api/account/description`

Updates the authenticated account's description.

### Authorization

| Header | Value |
|---|---|
| `Authorization` | Access token obtained from signin or signup. |

### Request Body

| Field | Type | Description |
|---|---|---|
| `description` | string | The new description. |

### Response `200`
```json
{
  "result": "success"
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `401` | Not logged in. | `not_logged_in` |
| `401` | Token expired. | `session_expired` |
| `401` | Invalid token. | `session_invalid` |
```json
{
  "detail": "detail_code"
}
```

---

## POST `/account/profile/upload`

Uploads a profile picture for the authenticated account. Image will be resized to 400x400 and saved as PNG and WebP.

### Authorization

| Header | Value |
|---|---|
| `Authorization` | Access token obtained from signin or signup. |

### Request Body

Multipart form upload with an image file. Max size: **10MB**.

### Response `200`
```json
{
  "result": "success",
  "hash": "abc123..."
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Invalid image file. | `invalid_image` |
| `401` | Not logged in. | `not_logged_in` |
| `401` | Token expired. | `session_expired` |
| `401` | Invalid token. | `session_invalid` |
| `413` | File size exceeds 10MB limit. | `file_too_large` |
```json
{
  "detail": "detail_code"
}
```

---

## POST `/account/banner/upload`

Uploads a banner for the authenticated account. Image will be resized to 1200x360 and saved as PNG and WebP.

### Authorization

| Header | Value |
|---|---|
| `Authorization` | Access token obtained from signin or signup. |

### Request Body

Multipart form upload with an image file. Max size: **15MB**.

### Response `200`
```json
{
  "result": "success",
  "hash": "abc123..."
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Invalid image file. | `invalid_image` |
| `401` | Not logged in. | `not_logged_in` |
| `401` | Token expired. | `session_expired` |
| `401` | Invalid token. | `session_invalid` |
| `413` | File size exceeds 15MB limit. | `file_too_large` |
```json
{
  "detail": "detail_code"
}
```