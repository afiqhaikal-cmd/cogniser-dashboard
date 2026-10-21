import json
from datetime import datetime
import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title='Cogniser | Factory Hygiene', page_icon='🏭', layout='wide')
STEPS = {1:['Temperature','Ear Ring','Necklace','Bracelet','Ring','Nail','Wound','Plaster'],2:['Hair Cover','Face Mask','Protective Clothing','Shoes'],3:['Hand Washing'],4:['Gloves'],5:['Mobile Phone / Metal Detection']}
ALL = [item for group in STEPS.values() for item in group]
for key, value in {'employee':None,'face':False,'checks':{},'history':[]}.items():
    if key not in st.session_state:
        st.session_state[key] = value

def outcome(checks):
    if len(checks) < len(ALL):
        return 'PENDING'
    return 'FAIL' if 'FAIL' in checks.values() else 'PASS'

def face_demo():
    st.session_state.employee = 'DEMO-001'
    st.session_state.face = True
    st.session_state.checks = {}

def save_demo():
    st.session_state.history.append({'Time':datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'Employee ID':st.session_state.employee,'Status':outcome(st.session_state.checks), 'PASS':sum(v=='PASS' for v in st.session_state.checks.values()),'FAIL':sum(v=='FAIL' for v in st.session_state.checks.values())})

def ppe_demo():
    if st.session_state.face:
        st.session_state.checks.update({'Gloves':'PASS','Face Mask':'FAIL','Hair Cover':'PASS'})
        save_demo()

def full_demo(passed):
    if not st.session_state.face:
        face_demo()
    st.session_state.checks = {key:'PASS' for key in ALL}
    if not passed:
        st.session_state.checks['Face Mask'] = 'FAIL'
    save_demo()

def reset_demo():
    st.session_state.employee = None
    st.session_state.face = False
    st.session_state.checks = {}
    st.session_state.history = []

@st.cache_data(ttl=15, show_spinner=False)
def fetch_events():
    try:
        url = st.secrets['SUPABASE_URL'].rstrip('/')
        key = st.secrets['SUPABASE_SECRET_KEY']
        response = requests.get(f'{url}/rest/v1/cogniser_events',headers={'apikey':key,'Authorization':f'Bearer {key}'},params={'select':'*','limit':'500'},timeout=15)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data,list):
            return [],'Unexpected Supabase response'
        return data,None
    except Exception as exc:
        return [],str(exc)

def decode_payload(event):
    for name in ('payload','raw_payload','event_payload','data','raw_data','metadata','body'):
        value = event.get(name)
        if isinstance(value,dict):
            return value
        if isinstance(value,list):
            return {'rectList':value}
        if isinstance(value,str):
            try:
                decoded = json.loads(value)
                if isinstance(decoded,dict):
                    return decoded
                if isinstance(decoded,list):
                    return {'rectList':decoded}
            except (ValueError,TypeError):
                pass
    return {}

def collect_codes(node, depth=0):
    if depth>6:
        return []
    found=[]
    if isinstance(node,dict):
        for k,v in node.items():
            if k.lower() in ('ppe','ppe_status','ppe_result','result','code','status','value','label','name','text') and isinstance(v,str):
                candidate=v.strip()
                if len(candidate)==5 and candidate[1]=='-' and candidate[3]=='-' and all(ch in '01' for ch in (candidate[0],candidate[2],candidate[4])):
                    found.append(candidate)
            if isinstance(v,(dict,list)):
                found.extend(collect_codes(v,depth+1))
    elif isinstance(node,list):
        for item in node:
            found.extend(collect_codes(item,depth+1))
    return found

def extract_attempts(payload):
    """Read Cogniser v49 detection_attempts without merging different attempts."""
    attempts = payload.get('detection_attempts', [])
    if not isinstance(attempts, list):
        return []
    results = []
    for i, attempt in enumerate(attempts, 1):
        if not isinstance(attempt, dict):
            continue
        raw = attempt.get('raw')
        obs = attempt.get('observations')
        if not isinstance(obs, dict):
            obs = {}
        bits = raw.split('-') if isinstance(raw, str) else []
        decoded = {}
        if len(bits) == 3 and all(bit in ('0', '1') for bit in bits):
            decoded = dict(zip(('gloves', 'face_mask', 'hair_cover'), ('PASS' if bit == '1' else 'FAIL' for bit in bits)))
        results.append({
            'Attempt': attempt.get('index', i),
            'Raw PPE': raw or 'Not provided',
            'Gloves': obs.get('gloves', decoded.get('gloves', 'UNKNOWN')),
            'Face Mask': obs.get('face_mask', decoded.get('face_mask', 'UNKNOWN')),
            'Hair Cover': obs.get('hair_cover', decoded.get('hair_cover', 'UNKNOWN')),
        })
    return results

def sorted_events(events):
    return sorted(events,key=lambda e:str(e.get('received_at') or e.get('created_at') or e.get('timestamp') or ''),reverse=True)

st.markdown('''<style>.block-container{max-width:1450px;padding-top:1.4rem}.hero{background:linear-gradient(100deg,#092f50,#086b83);color:white;border-radius:18px;padding:26px}.hero h1{color:white;margin:0}.hero p{color:#d5edf4;margin:6px 0 0}</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>COGNISER · FACTORY HYGIENE INSPECTION</h1><p>Face Recognition → Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Gate Eligibility</p></div>',unsafe_allow_html=True)
st.caption('REVIEWER PROTOTYPE · Cloud events may be manually submitted samples. CCTV/Cogniser hardware and physical gate are not verified or controlled by this web app.')

if st.button('Refresh Supabase Data'):
    fetch_events.clear()
    st.rerun()
events,error=fetch_events()
if error:
    st.error('Supabase connection error: '+error)
elif events:
    st.success(f'Supabase connected · {len(events)} events retrieved')
else:
    st.info('No cloud events available. You can still use Demo mode.')

mode=st.radio('Dashboard data source',['Cloud · Supabase','Demo · Simulation'],horizontal=True,disabled=not bool(events),index=0 if events else 1)
cloud = mode.startswith('Cloud') and bool(events)
if cloud:
    employee_ids=sorted({str(e.get('employee_id')) for e in events if e.get('employee_id') not in (None,'')})
    if not employee_ids:
        st.warning('No employee_id found in cloud records.')
        selected=None
    else:
        selected=st.selectbox('Select Employee ID · Cloud evidence',employee_ids,index=employee_ids.index('593037') if '593037' in employee_ids else 0)
    employee_events=sorted_events([e for e in events if str(e.get('employee_id'))==selected]) if selected else []
    face_events=[e for e in employee_events if str(e.get('event_type','')).lower()=='face']
    ppe_events=[e for e in employee_events if str(e.get('event_type','')).lower()=='ppe']
    codes=[]
    attempts=[]
    for event in ppe_events:
        payload = decode_payload(event)
        event_attempts = extract_attempts(payload)
        attempts.extend(event_attempts)
        codes.extend(str(item['Raw PPE']) for item in event_attempts if item['Raw PPE'] != 'Not provided')
        if not event_attempts:
            codes.extend(collect_codes(payload))
    # Only report individual components if the record has exactly one unambiguous PPE code.
    cloud_checks={}
    if len(codes)==1:
        bits=codes[0].split('-')
        cloud_checks={'Gloves':'PASS' if bits[0]=='1' else 'FAIL','Face Mask':'PASS' if bits[1]=='1' else 'FAIL','Hair Cover':'PASS' if bits[2]=='1' else 'FAIL'}
    checks=cloud_checks
    employee=selected
    status='PENDING' if face_events or ppe_events else 'READY'
    st.info('CLOUD EVIDENCE ONLY · Records below do not establish a complete 15-check inspection. No gate authorization is calculated from partial events.')
else:
    st.subheader('Try the demonstration')
    a,b,c,d,e=st.columns(5)
    a.button('1 · Face Recognition',on_click=face_demo,use_container_width=True)
    b.button('2 · PPE Sample (1-0-1)',on_click=ppe_demo,disabled=not st.session_state.face,use_container_width=True)
    c.button('3 · All PASS',on_click=full_demo,args=(True,),use_container_width=True)
    d.button('4 · Completed FAIL',on_click=full_demo,args=(False,),use_container_width=True)
    e.button('Reset Demo',on_click=reset_demo,use_container_width=True)
    checks=st.session_state.checks
    employee=st.session_state.employee
    status=outcome(checks) if st.session_state.face else 'READY'

colour='WHITE' if status=='READY' else 'BLUE' if status=='PENDING' else 'GREEN' if status=='PASS' else 'RED'
tabs=st.tabs(['LIVE OVERVIEW','FACE RECOGNITION','STEP 1 · HYGIENE','STEP 2 · PPE','STEP 3 · HAND WASHING','STEP 4 · GLOVES','STEP 5 · METAL DETECTION','AUDIT & REPORT','COGNISER CONNECTION','4-COLOUR INDICATOR'])
with tabs[0]:
    a,b,c=st.columns(3)
    a.metric('Employee ID',employee or 'Not detected')
    b.metric('Inspection Status · '+('Cloud evidence' if cloud else 'Demo'),status)
    c.metric('Checks confirmed · '+('Cloud' if cloud else 'Demo'),f'{len(checks)} / {len(ALL)}')
    st.dataframe(pd.DataFrame([{'Step':f'Step {step}','Checkpoint':item,'Result':checks.get(item,'PENDING')} for step,items in STEPS.items() for item in items]),hide_index=True,use_container_width=True)
with tabs[1]:
    st.header('Face Recognition · '+('Cloud' if cloud else 'Demo'))
    st.metric('Employee ID',employee or 'Not detected')
    if cloud:
        st.write(f'Face events for this employee: **{len(face_events)}**')
        if face_events:
            st.dataframe(pd.DataFrame(face_events),hide_index=True,use_container_width=True)
    else:
        st.caption('Use Face Recognition demo button above. DEMO-001 is synthetic.')
for step,idx in [(1,2),(2,3),(3,4),(4,5),(5,6)]:
    with tabs[idx]:
        st.header(f'Step {step} · '+('Cloud evidence' if cloud else 'Demo'))
        st.dataframe(pd.DataFrame([{'Checkpoint':item,'Result':checks.get(item,'PENDING'),'Source':('Cloud · one unambiguous PPE code' if cloud else 'Demo') if item in checks else 'Awaiting evidence'} for item in STEPS[step]]),hide_index=True,use_container_width=True)
        if cloud and step==2:
            st.write(f'PPE event records: **{len(ppe_events)}** · PPE codes extracted: **{len(codes)}**')
            if len(codes)!=1:
                st.warning('PPE component results are not automatically assigned because no single unambiguous 1-0-1 style code was found. Inspect raw payloads in Cogniser Connection. Multiple codes may refer to multiple people/attempts.')
            if attempts:
                st.subheader('Cogniser PPE detection attempts · Cloud evidence')
                st.dataframe(pd.DataFrame(attempts), hide_index=True, use_container_width=True)
                st.caption('Each row is a separate detection attempt, not a verified single-worker result. No component PASS/FAIL is assigned to the 15-check inspection when multiple attempts are present.')
            elif codes:
                st.write('Extracted PPE codes (gloves-mask-hair cover):', codes)
with tabs[7]:
    st.header('Audit & Report')
    if cloud:
        st.info('Cloud event history only. Not an official completed factory inspection audit.')
        if employee_events:
            st.dataframe(pd.DataFrame(employee_events),hide_index=True,use_container_width=True)
    elif st.session_state.history:
        df=pd.DataFrame(st.session_state.history)
        st.dataframe(df,hide_index=True,use_container_width=True)
        st.download_button('Download Demo Audit CSV',df.to_csv(index=False).encode('utf-8-sig'),'cogniser_demo_audit.csv','text/csv')
    else:
        st.info('No demo audit records yet.')
with tabs[8]:
    st.header('Cogniser Connection · Supabase')
    st.caption('Architecture target: local FastAPI + SQLite → sync process → Supabase → hosted dashboard. Automatic local-to-cloud sync and real Cogniser/CCTV connection are not verified.')
    if events:
        st.dataframe(pd.DataFrame(sorted_events(events)),hide_index=True,use_container_width=True)
        if cloud and employee_events:
            st.subheader('Selected employee · Raw event evidence')
            st.json(employee_events)
    else:
        st.info('No Supabase events returned.')
with tabs[9]:
    st.header('4-colour indicator · '+('Cloud evidence (not authorized)' if cloud else 'Simulation'))
    colors={'WHITE':'#ffffff','BLUE':'#2563eb','GREEN':'#16a34a','RED':'#dc2626'}
    cols=st.columns(4)
    for col,(name,shade) in zip(cols,colors.items()):
        with col:
            st.markdown(f'<div style="background:#f8fafc;padding:18px;border-radius:12px;text-align:center;border:{"3px solid #0284c7" if name==colour else "1px solid #cbd5e1"}"><div style="height:60px;width:60px;border-radius:50%;margin:auto;background:{shade};border:2px solid #64748b"></div><b style="color:#0f172a">{name}</b></div>',unsafe_allow_html=True)
    st.metric('Virtual indicator',colour)
    st.warning('No physical lamp, speaker, or gate is controlled. Cloud records never authorize entry in this prototype.')
