"""Incremental read-only Cogniser Supabase mirror: one checkpoint per accepted face event.
Deploy ONLY on hosted Streamlit, not factory Mini PC. Never scores PPE bits as PASS.
Existing mirror records are preserved across refreshes.
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
        # Incremental, idempotent mirror: NEVER delete or recreate mirrored history.
        # Keep all factory/local/manual records untouched.
        latest_face=None
        for r in records:
            eid=r.get('event_id'); typ=r.get('event_type')
            if not eid: continue
            p=_dict(r.get('payload')); emp=r.get('employee_id'); camera=r.get('camera_id'); when=r.get('event_time') or ''
            # Restore the face context even when this cloud event was mirrored earlier.
            # A repeated dashboard refresh must not create another checkpoint.
            existing=c.execute('SELECT local_event_id FROM cloud_event_map WHERE event_id=?',(str(eid),)).fetchone()
            if existing:
                if typ=='face':
                    mapped=c.execute('''SELECT a.id,a.employee_id FROM cloud_attempt_map m
                                        JOIN attempts a ON a.id=m.local_attempt_id
                                        WHERE m.event_id=? AND a.source='CLOUD_FACE_CHECKPOINT'
                                        ORDER BY m.position LIMIT 1''',(str(eid),)).fetchone()
                    if mapped:
                        latest_face={'employee':str(mapped['employee_id']),
                                     'camera':str(camera or ''),'attempt':mapped['id']}
                continue
            accepted=_accepted(p.get('accepted'))
            c.execute('INSERT OR REPLACE INTO cloud_evidence VALUES(?,?,?,?,?,?,?)',(eid,when,typ,emp,camera,str(accepted),json.dumps(p,ensure_ascii=False)))
            if typ not in ('face','ppe','manual_temperature','manual_inspection'):
                # All unknown/new event types are retained as evidence, not decisions.
                display = dict(p)
                display.update({'employee_id':emp, 'equipmentId':camera, 'original_event_type':typ})
                cur=c.execute('INSERT INTO events(time,event,payload,accepted,note) VALUES(?,?,?,?,?)',
                              (when,'cogniser_unknown_raw',json.dumps(display,ensure_ascii=False),int(accepted),
                               'Unverified event; no inspection decision'))
                c.execute('INSERT INTO cloud_event_map VALUES(?,?)',(eid,cur.lastrowid))
                continue
            display=dict(p); display.update({'employee_id':emp,'equipmentId':camera,'equipmentName':p.get('equipmentName') or camera,'accepted':accepted})
            if typ in ('manual_temperature','manual_inspection','cogniser_unknown'):
                kind = {'manual_temperature':'manual_temperature', 'manual_inspection':'manual_inspection', 'cogniser_unknown':'cogniser_unknown_raw'}[typ]
                display.update({'key':p.get('inspection_key'), 'result':p.get('inspection_result'),
                                'value_celsius':p.get('value_celsius'), 'operator_id':p.get('operator_id'),
                                'reason':p.get('manual_reason'), 'source':p.get('inspection_source')})
                cur=c.execute('INSERT INTO events(time,event,payload,accepted,note) VALUES(?,?,?,?,?)',
                              (when,kind,json.dumps(display,ensure_ascii=False),int(accepted),'Supabase read-only evidence'))
                c.execute('INSERT INTO cloud_event_map VALUES(?,?)',(eid,cur.lastrowid))
                if typ in ('manual_temperature','manual_inspection') and accepted:
                    # Associate only with latest open face checkpoint, matching employee, and a confirmed item.
                    key=p.get('inspection_key'); result=p.get('inspection_result')
                    if latest_face and str(emp)==latest_face['employee'] and key in ('temperature','ear_ring','necklace','bracelet','ring','nail','wound','plaster','hair_cover','face_mask','protective_clothing','shoes','hand_washing','gloves','mobile_phone') and result in ('PASS','FAIL'):
                        prior=c.execute('SELECT 1 FROM checks WHERE attempt_id=? AND key=?',(latest_face['attempt'],key)).fetchone()
                        if prior is None:
                            c.execute('INSERT INTO checks(attempt_id,key,status,source,time) VALUES(?,?,?,?,?)',
                                      (latest_face['attempt'],key,result,'CLOUD_MANUAL',when))
                            from core import recalculate
                            recalculate(c,latest_face['attempt'])
                        else:
                            c.execute('UPDATE events SET note=? WHERE id=?',('Duplicate/conflicting manual result; requires review',cur.lastrowid))
                    else:
                        c.execute('UPDATE events SET note=? WHERE id=?',('Manual evidence not linked to a verified face session',cur.lastrowid))
                continue
            if typ=='face':
                kind='cogniser_face_raw'
                display['score']=p.get('score'); display['faceLibName']=p.get('faceLibName','—')
            else:
                kind='cogniser_ppe_raw'; display['rectList']=_rects(p); display['taskName']=p.get('taskName','—')
            cur=c.execute('INSERT INTO events(time,event,payload,accepted,note) VALUES(?,?,?,?,?)',(when,kind,json.dumps(display,ensure_ascii=False),int(accepted),'Supabase read-only mirror'))
            face_event_id=cur.lastrowid
            c.execute('INSERT INTO cloud_event_map VALUES(?,?)',(eid,face_event_id))
            if typ=='face' and accepted and emp is not None:
                if latest_face:
                    c.execute("UPDATE attempts SET finished=?,reason=? WHERE id=? AND finished IS NULL",(when,'Superseded by next cloud face event',latest_face['attempt']))
                attempt=c.execute("INSERT INTO attempts(employee_id,started,stage,status,reason,source,face_session_id) VALUES(?,?,1,'PENDING',?,?,?)",(str(emp),when,'Awaiting mandatory verified inspection evidence','CLOUD_FACE_CHECKPOINT',face_event_id))
                latest_face={'employee':str(emp),'camera':str(camera or ''),'attempt':attempt.lastrowid}
                c.execute('INSERT INTO cloud_attempt_map VALUES(?,?,?)',(eid,0,attempt.lastrowid))
            elif typ=='ppe':
                rects=_rects(p)
                for pos,rect in enumerate(rects,1):
                    c.execute('INSERT OR REPLACE INTO cloud_ppe_attempts VALUES(?,?,?,?,?,?,?)',(eid,pos,emp,camera,str(rect.get('value','')),'UNVERIFIED',json.dumps({},ensure_ascii=False)))
                # Only a locally verified alarm may create FAIL. Never infer PASS from PPE bits.
                matched = (latest_face is not None and accepted
                           and str(emp) == latest_face['employee']
                           and bool(camera) and str(camera) == latest_face['camera']
                           and p.get('matching_status') == 'MATCHED')
                failed = p.get('failed_items')
                verified = p.get('ppe_mapping_verified') is True
                if matched and verified and p.get('alarm_only') is True and isinstance(failed, list):
                    allowed = {'gloves', 'hair_cover', 'face_mask', 'protective_clothing', 'shoes'}
                    # Future vendor-confirmed PPE items may be enabled through Streamlit secrets.
                    # Never accept arbitrary JSON item names as an automatic decision.
                    try:
                        import streamlit as st
                        configured = st.secrets.get('COGNISER_VERIFIED_PPE_ITEMS')
                        if isinstance(configured, (list, tuple)):
                            allowed = {str(v) for v in configured} & {
                                'ear_ring','necklace','bracelet','ring','nail','wound','plaster',
                                'hair_cover','face_mask','protective_clothing','shoes','gloves','mobile_phone'}
                    except (KeyError, TypeError, ValueError):
                        pass
                    from core import recalculate
                    for item in sorted(set(failed) & allowed):
                        prior = c.execute('SELECT 1 FROM checks WHERE attempt_id=? AND key=?',
                                          (latest_face['attempt'], item)).fetchone()
                        if prior is None:
                            c.execute('INSERT INTO checks(attempt_id,key,status,source,time) VALUES(?,?,?,?,?)',
                                      (latest_face['attempt'], item, 'FAIL', 'CLOUD_COGNISER_PPE_ALARM', when))
                            recalculate(c, latest_face['attempt'])
                    c.execute('UPDATE events SET note=? WHERE id=?',
                              ('Matched PPE alarm; locally verified FAIL items applied (vendor mapping must be validated)',face_event_id))
                elif not matched:
                    c.execute('UPDATE events SET note=? WHERE id=?',
                              ('PPE association unverified; raw evidence retained',face_event_id))
                else:
                    c.execute('UPDATE events SET note=? WHERE id=?',
                              ('PPE mapping or alarm status unverified; no check changed',face_event_id))
        c.commit()
    return len(records)
