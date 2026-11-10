"""Read-only Cogniser Supabase mirror: one checkpoint per accepted face event.
Deploy ONLY on hosted Streamlit, not factory Mini PC. Never scores PPE bits as PASS.
"""
import json
import urllib.parse
import urllib.request


def _dict(v):
    if isinstance(v, dict): return v
    if isinstance(v, str):
        try:
            d=json.loads(v)
            return d if isinstance(d,dict) else {}
        except (ValueError,TypeError): pass
    return {}


def _accepted(v):
    return v is True or v == 1 or (isinstance(v,str) and v.lower().strip() in ('true','1','yes'))


def _rects(payload):
    rects=payload.get('rectList')
    if isinstance(rects,list): return [r for r in rects if isinstance(r,dict)]
    out=[]
    for i,a in enumerate(payload.get('detection_attempts') or []):
        if not isinstance(a,dict): continue
        raw=a.get('raw')
        if isinstance(raw,dict): out.append({'id':str(raw.get('id',i)),'value':str(raw.get('value',''))})
        elif isinstance(raw,str): out.append({'id':str(i),'value':raw})
    return out


def refresh_cloud():
    import streamlit as st
    from core import connect
    url=st.secrets['SUPABASE_URL'].rstrip('/')
    key=st.secrets['SUPABASE_SECRET_KEY']
    records=[]; offset=0
    while True:
        query=urllib.parse.urlencode({'select':'*','order':'event_time.asc,event_id.asc','limit':500,'offset':offset})
        req=urllib.request.Request(url+'/rest/v1/cogniser_events?'+query,headers={'apikey':key,'Authorization':'Bearer '+key})
        with urllib.request.urlopen(req,timeout=25) as resp: chunk=json.load(resp)
        if not isinstance(chunk,list): raise RuntimeError('Unexpected Supabase response')
        records.extend(chunk)
        if len(chunk)<500: break
        offset+=len(chunk)

    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS cloud_evidence(event_id TEXT PRIMARY KEY,event_time TEXT,event_type TEXT,employee_id TEXT,camera_id TEXT,accepted TEXT,payload TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS cloud_ppe_attempts(event_id TEXT,attempt_index INTEGER,employee_id TEXT,camera_id TEXT,raw_value TEXT,overall_status TEXT,observations TEXT,PRIMARY KEY(event_id,attempt_index))')
        c.execute('CREATE TABLE IF NOT EXISTS cloud_event_map(event_id TEXT PRIMARY KEY,local_event_id INTEGER)')
        c.execute('CREATE TABLE IF NOT EXISTS cloud_attempt_map(event_id TEXT,position INTEGER,local_attempt_id INTEGER,PRIMARY KEY(event_id,position))')
        # Remove ONLY previous mirror-owned attempts/events. No factory or manual data.
        ids={r[0] for r in c.execute('SELECT local_attempt_id FROM cloud_attempt_map')}
        # Legacy online mirror source: never delete other sources.
        ids.update(r[0] for r in c.execute("SELECT id FROM attempts WHERE source='COGNISER_PPE_DETECTION' AND id NOT IN (SELECT local_attempt_id FROM cloud_attempt_map)"))
        ids.update(r[0] for r in c.execute("SELECT id FROM attempts WHERE source='CLOUD_FACE_CHECKPOINT'"))
        for aid in ids:
            c.execute('DELETE FROM checks WHERE attempt_id=?',(aid,))
            c.execute('DELETE FROM attempts WHERE id=?',(aid,))
        for (eid,) in c.execute('SELECT local_event_id FROM cloud_event_map').fetchall():
            c.execute('DELETE FROM events WHERE id=?',(eid,))
        for table in ('cloud_attempt_map','cloud_event_map','cloud_ppe_attempts','cloud_evidence'):
            c.execute('DELETE FROM '+table)
        latest_face=None
        for r in records:
            eid=r.get('event_id'); typ=r.get('event_type')
            if not eid: continue
            p=_dict(r.get('payload')); emp=r.get('employee_id'); camera=r.get('camera_id'); when=r.get('event_time') or ''
            accepted=_accepted(p.get('accepted'))
            c.execute('INSERT OR REPLACE INTO cloud_evidence VALUES(?,?,?,?,?,?,?)',(eid,when,typ,emp,camera,str(accepted),json.dumps(p,ensure_ascii=False)))
            if typ not in ('face','ppe'): continue
            display=dict(p); display.update({'employee_id':emp,'equipmentId':camera,'equipmentName':p.get('equipmentName') or camera,'accepted':accepted})
            if typ=='face':
                kind='cogniser_face_raw'
                display['score']=p.get('score'); display['faceLibName']=p.get('faceLibName','—')
            else:
                kind='cogniser_ppe_raw'; display['rectList']=_rects(p); display['taskName']=p.get('taskName','—')
            cur=c.execute('INSERT INTO events(time,event,payload,accepted,note) VALUES(?,?,?,?,?)',(when,kind,json.dumps(display,ensure_ascii=False),int(accepted),'Supabase read-only mirror'))
            face_event_id=cur.lastrowid
            c.execute('INSERT INTO cloud_event_map VALUES(?,?)',(eid,face_event_id))
            if typ=='face' and accepted and emp is not None and p.get('attempt_id') is not None:
                if latest_face:
                    c.execute("UPDATE attempts SET finished=?,reason=? WHERE id=? AND finished IS NULL",(when,'Superseded by next cloud face event',latest_face['attempt']))
                attempt=c.execute("INSERT INTO attempts(employee_id,started,stage,status,reason,source,face_session_id) VALUES(?,?,1,'PENDING',?,?,?)",(str(emp),when,'Awaiting mandatory verified inspection evidence','CLOUD_FACE_CHECKPOINT',face_event_id))
                latest_face={'employee':str(emp),'camera':str(camera or ''),'attempt':attempt.lastrowid}
                c.execute('INSERT INTO cloud_attempt_map VALUES(?,?,?)',(eid,0,attempt.lastrowid))
            elif typ=='ppe':
                rects=_rects(p)
                for pos,rect in enumerate(rects,1):
                    c.execute('INSERT OR REPLACE INTO cloud_ppe_attempts VALUES(?,?,?,?,?,?,?)',(eid,pos,emp,camera,str(rect.get('value','')),'UNVERIFIED',json.dumps({},ensure_ascii=False)))
                # Never infer PASS/FAIL from unverified PPE bit mapping.
                # Preserve received evidence, but do not create additional attempts.
                if latest_face and (str(emp)!=latest_face['employee'] or str(camera or '')!=latest_face['camera']):
                    c.execute('UPDATE events SET accepted=0,note=? WHERE id=?',('PPE identity/camera association unverified; raw evidence retained',face_event_id))
        c.commit()
    return len(records)
