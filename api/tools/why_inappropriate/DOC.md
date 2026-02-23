## GET `/api/tools/why_inappropriate`

Returns the indexes of inappropriate text based on PJSK's block and allow word lists for a given region.

### Request Body

| Field | Type | Description |
|---|---|---|
| `text` | string | The text to check. |
| `region` | string | The PJSK region to check against. |

### Response `200`
```json
{
  "indexes": [
    { "start": 0, "end": 5 },
    { "start": 12, "end": 20 }
  ]
}
```

`start` and `end` are character indexes into the original text indicating which ranges are inappropriate. Overlapping ranges are merged. An empty array means the text is clean.

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `400` | Text is too long (max 1024 characters). | `too_much_data` |
| `400` | Invalid request data. | `bad_request` |

```json
{
  "detail": "detail_code"
}
```