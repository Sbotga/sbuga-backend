## GET `/api/pjsk_data/current_event`

Returns the current PJSK event data including the top 100 leaderboard and ranking borders.

### Query Parameters

| Parameter | Type | Description |
|---|---|---|
| `region` | string | The PJSK region. `en` or `jp`. |

### Response `200`
```json
{
  "updated": 1700000000.0,
  "next_available_update": 1700000300.0,
  "event_id": 123,
  "event_status": "going",
  "top_100": {},
  "border": {}
}
```

`event_status` is one of `going`, `counting`, or `end`. Data is cached for **5 minutes** — `next_available_update` indicates when fresh data will be available.

### Response `200` (no active event)
```json
{
  "updated": 1700000000.0,
  "next_available_update": 1700000300.0,
  "event_id": null
}
```

### Errors

| Status | Detail | Detail Code |
|---|---|---|
| `503` | PJSK client unavailable. | `internal_server_error` |
| `503` | PJSK client maintainence. | `maintainence_pjsk` |

```json
{
  "detail": "detail_code"
}
```