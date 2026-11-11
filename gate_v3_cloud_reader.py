import json
import urllib.parse
import urllib.request


def fetch_gate_v3_snapshots(supabase_url, api_key):
    """Read simulation Gate V3 snapshots without modifying cloud data."""

    if not supabase_url or not api_key:
        raise ValueError("Supabase configuration missing")

    base = supabase_url.rstrip("/")

    params = urllib.parse.urlencode({
        "event_type": "eq.gate_snapshot",
        "select": "event_id,event_time,employee_id,event_type,payload",
        "order": "event_time.desc",
        "limit": "100"
    })

    url = base + "/rest/v1/cogniser_events?" + params

    request = urllib.request.Request(
        url,
        headers={
            "apikey": api_key,
            "Authorization": "Bearer " + api_key,
            "Accept": "application/json"
        },
        method="GET"
    )

    with urllib.request.urlopen(request, timeout=20) as response:
        records = json.load(response)

    if not isinstance(records, list):
        raise ValueError("Unexpected Supabase response")

    output = []

    for record in records:
        if record.get("event_type") != "gate_snapshot":
            continue

        payload = record.get("payload")

        try:
            if isinstance(payload, str):
                payload = json.loads(payload)
        except (ValueError, TypeError):
            continue

        if not isinstance(payload, dict):
            continue

        if payload.get("test_only") is not True:
            continue

        output.append({
            "event_id": record.get("event_id"),
            "event_time": record.get("event_time"),
            "employee_id": record.get("employee_id"),
            "event_type": "gate_snapshot",
            "payload": payload
        })

    return output
