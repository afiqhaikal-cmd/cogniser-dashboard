"""Cogniser V49 cloud mirror for Streamlit deployment.

Reconstructs a read-only representation of synced Face/PPE events and
PPE attempts. Does not POST to Supabase or control physical equipment.
Use on the online Streamlit deployment, not the original factory Mini PC.
"""
import json
import urllib.parse
import urllib.request


def _as_dict(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def _accepted(value):
    return value is True or value == 1 or (isinstance(value, str) and value.strip().lower() in ('true', '1', 'yes'))


def _attempts(payload):
    attempts = payload.get('detection_attempts') or []
    return attempts if isinstance(attempts, list) else []


def _rects(attempts):
    out = []
    for pos, attempt in enumerate(attempts):
        if not isinstance(attempt, dict):
            continue
        raw = attempt.get('raw')
        if isinstance(raw, dict):
            obj_id, value = raw.get('id', pos), raw.get('value', '')
        else:
            obj_id, value = pos, raw
        if isinstance(value, str):
            out.append({'id': str(obj_id), 'value': value})
    return out


def refresh_cloud():
    import streamlit as st
    from core import connect

    url = st.secrets['SUPABASE_URL'].rstrip('/')
    key = st.secrets['SUPABASE_SECRET_KEY']
    records, offset = [], 0
    while True:
        query = urllib.parse.urlencode({
            'select': '*', 'order': 'event_time.asc,event_id.asc',
            'limit': 500, 'offset': offset,
        })
        req = urllib.request.Request(
            url + '/rest/v1/cogniser_events?' + query,
            headers={'apikey': key, 'Authorization': 'Bearer ' + key},
        )
        with urllib.request.urlopen(req, timeout=25) as response:
            chunk = json.load(response)
        if not isinstance(chunk, list):
            raise RuntimeError('Invalid Supabase response')
        records.extend(chunk)
        if len(chunk) < 500:
            break
        offset += len(chunk)

    # Online mirror is rebuilt deterministically from cloud records.
    # This should only run against the online app's ephemeral database.
    with connect() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS cloud_evidence (
            event_id TEXT PRIMARY KEY, event_time TEXT, event_type TEXT,
            employee_id TEXT, camera_id TEXT, accepted TEXT, payload TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS cloud_ppe_attempts (
            event_id TEXT, attempt_index INTEGER, employee_id TEXT,
            camera_id TEXT, raw_value TEXT, overall_status TEXT,
            observations TEXT, PRIMARY KEY(event_id, attempt_index))''')
        c.execute('''CREATE TABLE IF NOT EXISTS cloud_event_map (
            event_id TEXT PRIMARY KEY, local_event_id INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS cloud_attempt_map (
            event_id TEXT, position INTEGER, local_attempt_id INTEGER,
            PRIMARY KEY(event_id, position))''')

        # Remove legacy cloud-mirror attempts created before cloud_attempt_map existed.
        # Scope is restricted to the hosted mirror's dedicated source marker.
        # Do not touch factory-originated inspection attempts.
        legacy_ids = [row[0] for row in c.execute(
            """SELECT id FROM attempts
               WHERE source = 'COGNISER_PPE_DETECTION'
                 AND id NOT IN (SELECT local_attempt_id FROM cloud_attempt_map)"""
        ).fetchall()]
        for legacy_id in legacy_ids:
            c.execute('DELETE FROM checks WHERE attempt_id=?', (legacy_id,))
            c.execute('DELETE FROM attempts WHERE id=?', (legacy_id,))

        # Only remove rows that this cloud bridge previously created.
        # Avoid modifying unrelated local or manually entered records.
        cloud_attempt_ids = [r[0] for r in c.execute(
            'SELECT local_attempt_id FROM cloud_attempt_map').fetchall()]
        for attempt_id in cloud_attempt_ids:
            c.execute('DELETE FROM checks WHERE attempt_id=?', (attempt_id,))
            c.execute('DELETE FROM attempts WHERE id=?', (attempt_id,))
        cloud_event_ids = [r[0] for r in c.execute(
            'SELECT local_event_id FROM cloud_event_map').fetchall()]
        for event_id in cloud_event_ids:
            c.execute('DELETE FROM events WHERE id=?', (event_id,))
        c.execute('DELETE FROM cloud_attempt_map')
        c.execute('DELETE FROM cloud_event_map')
        c.execute('DELETE FROM cloud_ppe_attempts')
        c.execute('DELETE FROM cloud_evidence')

        latest_face_id = None
        latest_employee = None
        for record in records:
            event_id = record.get('event_id')
            event_type = record.get('event_type')
            if not event_id:
                continue
            payload = _as_dict(record.get('payload'))
            event_time = record.get('event_time') or ''
            employee_id = record.get('employee_id')
            camera_id = record.get('camera_id')
            accepted = _accepted(payload.get('accepted'))
            c.execute('''INSERT OR REPLACE INTO cloud_evidence
                (event_id,event_time,event_type,employee_id,camera_id,accepted,payload)
                VALUES (?,?,?,?,?,?,?)''', (
                    event_id, event_time, event_type, employee_id, camera_id,
                    str(accepted), json.dumps(payload, ensure_ascii=False)))
            if event_type not in ('face', 'ppe'):
                continue

            display = dict(payload)
            display['employee_id'] = employee_id
            display['equipmentName'] = camera_id
            display['accepted'] = accepted
            if event_type == 'face':
                kind = 'cogniser_face_raw'
                display['score'] = payload.get('score')
                display['faceLibName'] = payload.get('faceLibName', '—')
            else:
                kind = 'cogniser_ppe_raw'
                attempts = _attempts(payload)
                display['rectList'] = _rects(attempts)
                # Cloud sync did not preserve taskName; do not invent it.
                display['taskName'] = payload.get('taskName', '—')
            cur = c.execute('''INSERT INTO events(time,event,payload,accepted,note)
                VALUES(?,?,?,?,?)''', (
                    event_time, kind, json.dumps(display, ensure_ascii=False),
                    int(accepted), 'Cloud mirror · reconstructed from Supabase'))
            local_event_id = cur.lastrowid
            c.execute('INSERT INTO cloud_event_map VALUES(?,?)', (event_id, local_event_id))

            if event_type == 'face' and accepted:
                latest_face_id = local_event_id
                latest_employee = str(employee_id) if employee_id is not None else None
            elif event_type == 'ppe':
                attempts = _attempts(payload)
                for position, attempt in enumerate(attempts, 1):
                    if not isinstance(attempt, dict):
                        continue
                    raw = attempt.get('raw')
                    if isinstance(raw, dict):
                        raw_value = raw.get('value')
                    else:
                        raw_value = raw
                    c.execute('''INSERT OR REPLACE INTO cloud_ppe_attempts
                        (event_id,attempt_index,employee_id,camera_id,raw_value,overall_status,observations)
                        VALUES(?,?,?,?,?,?,?)''', (
                            event_id, position, employee_id, camera_id,
                            json.dumps(raw_value, ensure_ascii=False) if isinstance(raw_value, (dict,list)) else str(raw_value) if raw_value is not None else None,
                            payload.get('overall_status', 'PENDING_OR_UNVERIFIED'),
                            json.dumps(attempt.get('observations'), ensure_ascii=False)))
                    # Only create a dashboard attempt when a face session can
                    # be associated by the already-prototyped event ordering.
                    if not accepted or latest_face_id is None:
                        continue
                    if str(employee_id) != latest_employee:
                        continue
                    cur = c.execute('''INSERT INTO attempts
                        (employee_id,started,finished,stage,status,reason,source,face_session_id)
                        VALUES(?,?,NULL,1,'PENDING',?,?,?)''', (
                            str(employee_id), event_time,
                            'Cloud PPE evidence; mandatory checks unverified',
                            'COGNISER_PPE_DETECTION', latest_face_id))
                    c.execute('INSERT INTO cloud_attempt_map VALUES(?,?,?)',
                              (event_id, position, cur.lastrowid))
        c.commit()
    return len(records)
