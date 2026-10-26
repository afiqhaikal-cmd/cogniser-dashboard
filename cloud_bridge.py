"""Read-only Supabase event mirror into SQLite.

Supports Cogniser V49 Face and PPE event records.
Does not modify the original inspection or event tables.
"""

import json
import urllib.request
import urllib.parse


def refresh_cloud():
    import streamlit as st
    from core import connect

    url = st.secrets["SUPABASE_URL"].rstrip("/")
    key = st.secrets["SUPABASE_SECRET_KEY"]

    records = []
    offset = 0

    # 1. Retrieve all cloud events from Supabase.
    while True:
        query = urllib.parse.urlencode({
            "select": "*",
            "order": "event_time.asc",
            "limit": 500,
            "offset": offset
        })

        request = urllib.request.Request(
            url + "/rest/v1/cogniser_events?" + query,
            headers={
                "apikey": key,
                "Authorization": "Bearer " + key
            }
        )

        with urllib.request.urlopen(request, timeout=25) as response:
            chunk = json.load(response)

        if not isinstance(chunk, list):
            raise RuntimeError("Invalid Supabase response")

        records.extend(chunk)

        if len(chunk) < 500:
            break

        offset += len(chunk)

    # 2. Prepare cloud evidence tables.
    with connect() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cloud_evidence (
                event_id TEXT PRIMARY KEY,
                event_time TEXT,
                event_type TEXT,
                employee_id TEXT,
                camera_id TEXT,
                accepted TEXT,
                payload TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cloud_ppe_attempts (
                event_id TEXT,
                attempt_index INTEGER,
                employee_id TEXT,
                camera_id TEXT,
                raw_value TEXT,
                overall_status TEXT,
                observations TEXT,
                PRIMARY KEY (event_id, attempt_index)
            )
        """)

        # These are mirror tables only.
        # Original local inspection tables are untouched.
        conn.execute("DELETE FROM cloud_evidence")
        conn.execute("DELETE FROM cloud_ppe_attempts")

        # 3. Store Face and PPE cloud records.
        for record in records:

            payload = record.get("payload") or {}

            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    payload = {}

            if not isinstance(payload, dict):
                payload = {}

            event_id = record.get("event_id")
            event_type = record.get("event_type")
            employee_id = record.get("employee_id")
            camera_id = record.get("camera_id")

            conn.execute("""
                INSERT OR REPLACE INTO cloud_evidence
                (
                    event_id,
                    event_time,
                    event_type,
                    employee_id,
                    camera_id,
                    accepted,
                    payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                record.get("event_time"),
                event_type,
                employee_id,
                camera_id,
                str(payload.get("accepted", "")),
                json.dumps(payload, ensure_ascii=False)
            ))

            # 4. Extract PPE detection attempts.
            if event_type == "ppe":

                attempts = payload.get("detection_attempts") or []

                if not isinstance(attempts, list):
                    attempts = []

                for position, attempt in enumerate(attempts, start=1):

                    if not isinstance(attempt, dict):
                        continue

                    attempt_index = attempt.get("index")

                    if attempt_index is None:
                        attempt_index = position

                    try:
                        attempt_index = int(attempt_index)
                    except (TypeError, ValueError):
                        attempt_index = position

                    raw_value = attempt.get("raw")

                    if isinstance(raw_value, (dict, list)):
                        raw_value = json.dumps(
                            raw_value,
                            ensure_ascii=False
                        )

                    observations = attempt.get("observations")

                    conn.execute("""
                        INSERT OR REPLACE INTO cloud_ppe_attempts
                        (
                            event_id,
                            attempt_index,
                            employee_id,
                            camera_id,
                            raw_value,
                            overall_status,
                            observations
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_id,
                        attempt_index,
                        employee_id,
                        camera_id,
                        str(raw_value) if raw_value is not None else None,
                        payload.get("overall_status", "PENDING_OR_UNVERIFIED"),
                        json.dumps(observations, ensure_ascii=False)
                    ))

        conn.commit()

    return len(records)
