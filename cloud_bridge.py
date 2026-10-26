"""Cogniser V49 - Supabase Cloud Bridge.

Mirrors cloud events into an ephemeral SQLite database.
Reconstructs Face and PPE events for the original V49 dashboard.

Cloud events are read-only.
No physical hardware or gate control.
"""

import json
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime, timezone


def refresh_cloud():
    import streamlit as st
    from core import connect

    url = st.secrets["SUPABASE_URL"].rstrip("/")
    key = st.secrets["SUPABASE_SECRET_KEY"]

    records = []
    offset = 0

    # --------------------------------------------------
    # 1. DOWNLOAD SUPABASE EVENTS
    # --------------------------------------------------
    while True:
        query = urllib.parse.urlencode({
            "select": "*",
            "order": "event_time.asc,event_id.asc",
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

    # --------------------------------------------------
    # 2. PREPARE MIRROR TABLES
    # --------------------------------------------------
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

        conn.execute("""
            CREATE TABLE IF NOT EXISTS cloud_event_map (
                event_id TEXT PRIMARY KEY,
                local_event_id INTEGER
            )
        """)

        conn.execute("DELETE FROM cloud_evidence")
        conn.execute("DELETE FROM cloud_ppe_attempts")

        # --------------------------------------------------
        # 3. RECONSTRUCT ORIGINAL V49 EVENTS
        # --------------------------------------------------
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
            event_time = record.get("event_time")

            conn.execute("""
                INSERT OR REPLACE INTO cloud_evidence
                (
                    event_id, event_time, event_type,
                    employee_id, camera_id, accepted, payload
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id,
                event_time,
                event_type,
                employee_id,
                camera_id,
                str(payload.get("accepted", "")),
                json.dumps(payload, ensure_ascii=False)
            ))

            if event_type not in ("face", "ppe"):
                continue

            # Build dashboard-compatible event payload.
            dashboard_payload = dict(payload)

            dashboard_payload["employee_id"] = employee_id
            dashboard_payload["equipmentName"] = camera_id
            dashboard_payload["accepted"] = bool(
                payload.get("accepted", False)
            )

            if event_type == "face":

                original_event_name = "cogniser_face_raw"

                dashboard_payload["score"] = payload.get("score")
                dashboard_payload["faceLibName"] = payload.get(
                    "faceLibName", "CLOUD"
                )

                note = "Cloud mirrored Face Recognition event"

            else:

                original_event_name = "cogniser_ppe_raw"

                attempts = payload.get("detection_attempts") or []

                if not isinstance(attempts, list):
                    attempts = []

                rects = []

                for position, attempt in enumerate(attempts, start=1):

                    if not isinstance(attempt, dict):
                        continue

                    raw = attempt.get("raw")

                    if isinstance(raw, dict):
                        object_id = raw.get("id", position - 1)
                        value = raw.get("value", "")
                    else:
                        object_id = position - 1
                        value = raw or ""

                    rects.append({
                        "id": str(object_id),
                        "value": str(value)
                    })

                    attempt_index = attempt.get("index", position)

                    try:
                        attempt_index = int(attempt_index)
                    except (TypeError, ValueError):
                        attempt_index = position

                    conn.execute("""
                        INSERT OR REPLACE INTO cloud_ppe_attempts
                        (
                            event_id, attempt_index,
                            employee_id, camera_id,
                            raw_value, overall_status, observations
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        event_id,
                        attempt_index,
                        employee_id,
                        camera_id,
                        str(value),
                        payload.get(
                            "overall_status",
                            "PENDING_OR_UNVERIFIED"
                        ),
                        json.dumps(
                            attempt.get("observations"),
                            ensure_ascii=False
                        )
                    ))

                dashboard_payload["rectList"] = rects
                dashboard_payload["taskName"] = payload.get(
                    "taskName",
                    "Gloves, headgear mask recognition"
                )

                note = "Cloud mirrored PPE Detection event"

            # Avoid duplicating events during Streamlit refresh.
            existing = conn.execute(
                "SELECT local_event_id FROM cloud_event_map "
                "WHERE event_id = ?",
                (event_id,)
            ).fetchone()

            if existing:
                conn.execute("""
                    UPDATE events
                    SET time = ?, event = ?, payload = ?,
                        accepted = ?, note = ?
                    WHERE id = ?
                """, (
                    event_time,
                    original_event_name,
                    json.dumps(
                        dashboard_payload,
                        ensure_ascii=False
                    ),
                    int(dashboard_payload["accepted"]),
                    note,
                    existing["local_event_id"]
                ))

            else:
                cursor = conn.execute("""
                    INSERT INTO events
                    (time, event, payload, accepted, note)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    event_time,
                    original_event_name,
                    json.dumps(
                        dashboard_payload,
                        ensure_ascii=False
                    ),
                    int(dashboard_payload["accepted"]),
                    note
                ))

                conn.execute("""
                    INSERT INTO cloud_event_map
                    (event_id, local_event_id)
                    VALUES (?, ?)
                """, (
                    event_id,
                    cursor.lastrowid
                ))

        conn.commit()

    return len(records)
