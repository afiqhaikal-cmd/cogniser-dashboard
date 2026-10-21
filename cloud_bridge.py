"""Read-only Supabase event mirror for hosted review of original V49 dashboard.
Cloud evidence is not proof of commissioned CCTV or validated person association.
"""
import json, os, sqlite3
import requests
import streamlit as st
from core import connect, time


def refresh_cloud():
    url = st.secrets['SUPABASE_URL'].rstrip('/')
    key = st.secrets['SUPABASE_SECRET_KEY']
    r = requests.get(f'{url}/rest/v1/cogniser_events', headers={'apikey': key, 'Authorization': f'Bearer {key}'},
                     params={'select':'*','order':'received_at.asc','limit':'1000'}, timeout=20)
    r.raise_for_status()
    events = r.json()
    with connect() as c:
        # Hosted mirror only. Keep database state deterministic on each refresh.
        c.execute('DELETE FROM checks'); c.execute('DELETE FROM attempts'); c.execute('DELETE FROM events')
        face_id = None
        employee = None
        for row in events:
            kind = str(row.get('event_type') or '').lower()
            payload = row.get('payload') or {}
            if isinstance(payload, str):
                try: payload = json.loads(payload)
                except ValueError: payload = {}
            if not isinstance(payload, dict): payload = {}
            emp = str(row.get('employee_id') or payload.get('employee_id') or '').strip()
            timestamp = str(row.get('received_at') or row.get('event_time') or time())
            if kind == 'face':
                employee = emp or None
                evidence = dict(payload)
                evidence['employee_id'] = emp
                evidence.setdefault('equipmentName',row.get('camera_id'))
                cur = c.execute('INSERT INTO events(time,event,payload,accepted,note) VALUES(?,?,?,?,?)',
                    (timestamp,'cogniser_face_raw',json.dumps(evidence,ensure_ascii=False),int(bool(emp)),
                     'Cloud mirror: source/identity threshold unverified'))
                face_id = cur.lastrowid if emp else None
            elif kind == 'ppe':
                evidence = dict(payload)
                evidence['employee_id'] = emp
                evidence.setdefault('equipmentName',row.get('camera_id'))
                detections = evidence.get('detection_attempts') or []
                if not isinstance(detections,list): detections = []
                cur = c.execute('INSERT INTO events(time,event,payload,accepted,note) VALUES(?,?,?,?,?)',
                    (timestamp,'cogniser_ppe_raw',json.dumps(evidence,ensure_ascii=False),int(bool(detections and emp)),
                     'Cloud mirror: PPE rectangles are unverified worker association'))
                # Reconstruct original V49 audit structure, but do not assert real identity association.
                for detection in detections:
                    if not isinstance(detection,dict):continue
                    observations=detection.get('observations') or {}
                    if not isinstance(observations,dict):continue
                    clean={k:str(v).upper() for k,v in observations.items()
                           if k in ('gloves','face_mask','hair_cover') and str(v).upper() in ('PASS','FAIL')}
                    if not clean:continue
                    a=c.execute('INSERT INTO attempts(employee_id,started,stage,status,reason,source,face_session_id) VALUES(?,?,?,?,?,?,?)',
                        (emp,timestamp,1,'PENDING','Cloud PPE evidence only; identity association and other checks unverified',
                         'COGNISER_PPE_DETECTION',face_id if employee == emp else None))
                    for k,v in clean.items():
                        c.execute('INSERT INTO checks(attempt_id,key,status,source,time) VALUES(?,?,?,?,?)',
                            (a.lastrowid,k,v,'SUPABASE_CLOUD_EVIDENCE',timestamp))
        c.commit()
    return len(events)
