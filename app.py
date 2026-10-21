import streamlit as st
import pandas as pd
from datetime import datetime
import requests

def get_cogniser_events():
    try:
        url = st.secrets["SUPABASE_URL"].rstrip("/")
        key = st.secrets["SUPABASE_SECRET_KEY"]

        response = requests.get(
            f"{url}/rest/v1/cogniser_events",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
            },
            params={
                "select": "*",
                "order": "event_id.desc",
                "limit": "100",
            },
            timeout=15,
        )

        response.raise_for_status()
        return response.json(), None

    except Exception as e:
        return [], str(e)
    st.set_page_config(page_title='Cogniser | Reviewer Demo',page_icon='🏭',layout='wide')
STEPS={1:['Temperature','Ear Ring','Necklace','Bracelet','Ring','Nail','Wound','Plaster'],2:['Hair Cover','Face Mask','Protective Clothing','Shoes'],3:['Hand Washing'],4:['Gloves'],5:['Mobile Phone / Metal Detection']}
ALL=[k for v in STEPS.values() for k in v]
if 'records' not in st.session_state: st.session_state.records=[]
if 'checks' not in st.session_state: st.session_state.checks={}
if 'employee' not in st.session_state: st.session_state.employee=None
if 'face' not in st.session_state: st.session_state.face=False
if 'history' not in st.session_state: st.session_state.history=[]
if 'scenario' not in st.session_state: st.session_state.scenario='Ready'
def outcome(checks):
 if len(checks)<len(ALL):return 'PENDING'
 return 'FAIL' if 'FAIL' in checks.values() else 'PASS'
def save():
 if st.session_state.employee:
  st.session_state.history.append({'Time':datetime.now().strftime('%Y-%m-%d %H:%M:%S'),'Employee ID':st.session_state.employee,'Status':outcome(st.session_state.checks),'PASS':sum(x=='PASS' for x in st.session_state.checks.values()),'FAIL':sum(x=='FAIL' for x in st.session_state.checks.values()),'PENDING':len(ALL)-len(st.session_state.checks)})
def face():
 st.session_state.employee='DEMO-001';st.session_state.face=True;st.session_state.checks={};st.session_state.scenario='Face detected'
def ppe():
 if not st.session_state.face:return
 # Sample 1-0-1: gloves PASS, mask FAIL, hair cover PASS
 st.session_state.checks.update({'Gloves':'PASS','Face Mask':'FAIL','Hair Cover':'PASS'});st.session_state.scenario='PPE sample received';save()
def full(passed):
 if not st.session_state.face:face()
 st.session_state.checks={k:'PASS' for k in ALL}
 if not passed:st.session_state.checks['Face Mask']='FAIL'
 st.session_state.scenario='Complete sample';save()
def reset():
 st.session_state.employee=None;st.session_state.face=False;st.session_state.checks={};st.session_state.history=[];st.session_state.scenario='Ready'
st.markdown('''<style>.block-container{max-width:1450px;padding-top:1.4rem}.hero{background:linear-gradient(100deg,#092f50,#086b83);color:white;border-radius:18px;padding:26px}.hero h1{color:white;margin:0}.hero p{color:#d5edf4;margin:6px 0 0}</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>COGNISER · FACTORY HYGIENE INSPECTION</h1><p>Face Recognition → Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Gate Eligibility</p></div>',unsafe_allow_html=True)
st.warning('REVIEWER DEMO ONLY · Synthetic employee ID · No real CCTV, sensors, speaker, gate, or factory database connection. Demo data is limited to this browser session.')
st.subheader('Try the demonstration')
a,b,c,d,e=st.columns(5)
a.button('1 · Face Recognition',on_click=face,use_container_width=True)
b.button('2 · PPE Sample (1-0-1)',on_click=ppe,disabled=not st.session_state.face,use_container_width=True)
c.button('3 · All PASS',on_click=full,args=(True,),use_container_width=True)
d.button('4 · Completed FAIL',on_click=full,args=(False,),use_container_width=True)
e.button('Reset Demo',on_click=reset,use_container_width=True)
checks=st.session_state.checks;status=outcome(checks) if st.session_state.face else 'READY'
colour='WHITE' if status=='READY' else 'BLUE' if status=='PENDING' else 'GREEN' if status=='PASS' else 'RED'
hexes={'WHITE':'#ffffff','BLUE':'#2563eb','GREEN':'#16a34a','RED':'#dc2626'}
tabs=st.tabs(['LIVE OVERVIEW','FACE RECOGNITION','STEP 1 · HYGIENE','STEP 2 · PPE','STEP 3 · HAND WASHING','STEP 4 · GLOVES','STEP 5 · METAL DETECTION','AUDIT & REPORT','COGNISER CONNECTION','4-COLOUR INDICATOR'])
with tabs[0]:
 x,y,z=st.columns(3);x.metric('Employee ID',st.session_state.employee or 'Not detected');y.metric('Inspection Status',status);z.metric('Checks completed',f'{len(checks)} / {len(ALL)}')
 st.info('A PPE detection updates component checks. The overall inspection remains PENDING until every mandatory check is recorded.')
 st.dataframe(pd.DataFrame([{'Step':f'Step {step}','Checkpoint':key,'Result':checks.get(key,'PENDING')} for step,keys in STEPS.items() for key in keys]),hide_index=True,use_container_width=True)
with tabs[1]:
    st.header("Face Recognition")

    st.subheader("Demo Session")
    st.metric(
        "Demo Employee",
        st.session_state.employee or "Not detected"
    )

    st.subheader("Supabase Face Recognition Events")

    cloud_events, cloud_error = get_cogniser_events()

    if cloud_error:
        st.error(f"Supabase error: {cloud_error}")
    else:
        face_events = [
            event for event in cloud_events
            if event.get("event_type") == "face"
        ]

        if face_events:
            st.dataframe(
                pd.DataFrame(face_events)[
                    ["employee_id", "camera_id", "event_time"]
                ],
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No face recognition events found.")
 with tabs[idx]:
  st.header(f'Step {step} · Inspection');st.dataframe(pd.DataFrame([{'Checkpoint':k,'Result':checks.get(k,'PENDING'),'Source':'DEMO' if k in checks else 'Awaiting evidence'} for k in STEPS[step]]),hide_index=True,use_container_width=True)
with tabs[7]:
 st.header('Monthly Audit · Demo Session')
 if st.session_state.history:
  df=pd.DataFrame(st.session_state.history);st.dataframe(df,use_container_width=True,hide_index=True);st.download_button('Download Demo Audit CSV',df.to_csv(index=False).encode('utf-8-sig'),'cogniser_demo_audit.csv','text/csv')
 else:st.info('Run a PPE or completed inspection sample to create a demo audit record.')
 st.caption('This demo audit is not an official factory form or persistent inspection record.')
with tabs[8]:
 st.header('Integration Status');st.info('Offline sample simulation in hosted web mode. FastAPI receiver and real CCTV feeds are NOT connected.')
 st.write('Original prototype architecture: Dahua CCTV / Cogniser V1 → FastAPI → SQLite → Streamlit dashboard. This hosted review version is a standalone demonstration.')
 st.caption('Server Room: BMAX B1 Plus Mini PC and Cogniser V1. LAB: two Dahua IPC-HFW2441S-S cameras; edge device and speaker models not yet selected.')
with tabs[9]:
 st.header('Four-colour indicator · SIMULATION ONLY')
 cols=st.columns(4)
 for col,name in zip(cols,hexes):
  with col:
   selected=name==colour
   st.markdown(f'<div style="border:{"3px solid #0284c7" if selected else "1px solid #cbd5e1"};background:#f8fafc;padding:20px;border-radius:14px;text-align:center"><div style="height:65px;width:65px;border-radius:50%;margin:auto;background:{hexes[name]};border:2px solid #64748b"></div><b style="color:#0f172a">{name}</b></div>',unsafe_allow_html=True)
 st.metric('Virtual signal',colour)
 st.info({'WHITE':'Ready / Standby','BLUE':'Processing / Awaiting checks','GREEN':'Passed / Authorized (simulation)','RED':'Failed / Unauthorized (simulation)'}[colour])
 st.warning('No physical lamp, speaker, or gate is controlled by this demo.')
st.divider()
st.subheader("Live Supabase Events")

if st.button("Refresh Supabase Data"):
    st.rerun()

events, error = get_cogniser_events()

if error:
    st.error(f"Supabase connection error: {error}")
elif events:
    df_events = pd.DataFrame(events)

    st.success(f"Connected to Supabase — {len(df_events)} events retrieved")

    preferred_columns = [
        "event_type",
        "employee_id",
        "camera_id",
        "event_id",
    ]

    available_columns = [
        col for col in preferred_columns
        if col in df_events.columns
    ]

    st.dataframe(
        df_events[available_columns],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("Connected to Supabase, but no events found.")
