## GET `/api/checks/username/{username}`

Checks if a username is taken.

### Response `200`

Username is taken.
```json
{
  "id": 1234567890,
  "username": "example",
  "display_name": "Example"
}
```

### Response `404`

Username is available.