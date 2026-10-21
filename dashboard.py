import streamlit as st,pandas as pd,sqlite3
from core import connect,snapshot,STEPS,LABEL,ORANGE,MANUAL
import json
STEP_NAMES=['Temperature + Jewellery / Nail / Wound / Plaster','Hair Cover / Mask / Clothing / Shoes','Hand Washing','Gloves','Mobile Phone / Metal Detection']
st.set_page_config(page_title='Cogniser | Original Factory Checkpoints',layout='wide',page_icon='🏭')
st.markdown('''<style>.block-container{max-width:1450px;padding-top:1.4rem}.hero{background:linear-gradient(100deg,#092f50,#086b83);color:white;border-radius:18px;padding:26px}.hero h1{color:white;margin:0}.hero p{color:#d5edf4;margin:6px 0 0}.tile{border:1px solid #cbd5e1;border-radius:12px;padding:16px;min-height:145px;background:#f8fafc}.tag{font-size:12px;color:#64748b}.signal{width:110px;height:110px;border-radius:100%;margin:12px auto;border:6px solid white;box-shadow:0 0 24px #9ca3af}</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>COGNISER · ORIGINAL FACTORY INSPECTION v49</h1><p>Face Recognition → Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Gate Eligibility</p></div>',unsafe_allow_html=True)
st.caption('LIVE DATA REFRESH 5 SECONDS · LIVE DATA RECEIVER PROTOTYPE · Only explicit confirmed events change results. Hardware control and Cogniser event mapping require commissioning.')
s=snapshot();a=s['active'];last=s['latest'];current=a or last;state=(a['status'] if a else (last['status'] if last else 'WAITING'));color={'READY':'#ffffff','PASS':'#16a34a','FAIL':'#dc2626','WAITING':'#ffffff','PENDING':'#2563eb','INTERRUPTED':'#64748b'}.get(state,'#64748b')
def latest_ppe_component_results():
 """Read the latest accepted PPE rectangle for the current face event.
 Do not rely on the active attempt or an earlier session's checks.
 """
 with connect() as c:
  face=c.execute("SELECT id,payload FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
  if not face:return {}
  employee=str(json.loads(face['payload']).get('employee_id',''))
  # A PPE event is only applicable after the current face event, for that employee.
  raws=c.execute("SELECT id,payload FROM events WHERE event='cogniser_ppe_raw' AND accepted=1 AND id>? ORDER BY id DESC",(face['id'],)).fetchall()
  for raw in raws:
   evidence=json.loads(raw['payload'])
   if str(evidence.get('employee_id',''))!=employee:continue
   detections=evidence.get('detection_attempts') or []
   if detections:
    obs=detections[-1].get('observations') or {}
    if obs:return {k:v for k,v in obs.items() if v in ('PASS','FAIL')}
  # Persisted checks are fallback only for this exact face session.
  row=c.execute("SELECT id FROM attempts WHERE face_session_id=? AND employee_id=? AND source='COGNISER_PPE_DETECTION' ORDER BY id DESC LIMIT 1",(face['id'],employee)).fetchone()
  if row:
   rows=c.execute("SELECT key,status FROM checks WHERE attempt_id=? AND key IN ('gloves','face_mask','hair_cover')",(row['id'],)).fetchall()
   return {r['key']:r['status'] for r in rows}
 return {}

def face_ppe_diagnostics():
 with connect() as c:
  face=c.execute("SELECT id,payload FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
  if not face:return 'No accepted Face Recognition event in this database.'
  employee=str(json.loads(face['payload']).get('employee_id',''))
  events=c.execute("SELECT accepted,payload FROM events WHERE event='cogniser_ppe_raw' AND id>? ORDER BY id DESC",(face['id'],)).fetchall()
  if not events:return f'Face ID {employee} received; no PPE event has been received after this face event.'
  good=[e for e in events if e['accepted'] and str(json.loads(e['payload']).get('employee_id',''))==employee]
  if not good:return f'{len(events)} PPE event(s) received, but none accepted for Face ID {employee}. Check the PPE test response and event order.'
  return f'{len(good)} accepted PPE message(s) linked to Face ID {employee}; component results should be visible.'

def virtual_hardware_status():
 """Four-colour display simulation only; never issue physical outputs."""
 snap=snapshot()
 active=snap['active']; last=snap['latest']
 with connect() as c:
  face=c.execute("SELECT id FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
  count=c.execute("SELECT COUNT(*) FROM attempts WHERE face_session_id=? AND source='COGNISER_PPE_DETECTION'",(face['id'],)).fetchone()[0] if face else 0
 if active:
  return ('PROCESSING','BLUE','Pemeriksaan sedang dijalankan.',count)
 if last and last['status']=='PASS':
  return ('PASS','GREEN','Pemeriksaan lulus.',count)
 if last and last['status']=='FAIL':
  return ('FAIL','RED','Pemeriksaan gagal. Sila dapatkan bantuan.',count)
 return ('READY','WHITE','Sistem sedia untuk pemeriksaan.',count)

@st.fragment(run_every="5s")
def hardware_simulation():
 status,colour,audio,count=virtual_hardware_status()
 st.subheader('Four-colour status indicator · SIMULATION ONLY')
 st.caption('Meeting 8 October 2026: WHITE=Ready, BLUE=Processing, GREEN=Passed, RED=Failed. No lamp, speaker or edge device is connected.')
 colours={'WHITE':'#ffffff','BLUE':'#2563eb','GREEN':'#16a34a','RED':'#dc2626'}
 labels={'WHITE':'READY / STANDBY','BLUE':'PROCESSING / DETECTING','GREEN':'PASSED / AUTHORIZED','RED':'FAILED / UNAUTHORIZED'}
 cols=st.columns(4)
 for col,(name,hexcolour) in zip(cols,colours.items()):
  selected=(colour==name)
  with col:
   st.markdown(f'<div style="background:{"#e0f2fe" if selected else "#f8fafc"};border:{"3px solid #0284c7" if selected else "1px solid #cbd5e1"};padding:18px;border-radius:14px;text-align:center"><div style="margin:auto;width:64px;height:64px;border-radius:50%;background:{hexcolour};border:2px solid #64748b;box-shadow:{"0 0 20px #38bdf8" if selected else "none"}"></div><b style="color:#0f172a">{name}</b><div style="color:#334155;font-size:12px">{labels[name]}</div></div>',unsafe_allow_html=True)
 a,b,c=st.columns(3)
 a.metric('Current virtual signal',colour)
 b.metric('Inspection state',status)
 c.metric('PPE attempts · current face',count)
 st.info('Speaker message preview: '+audio)
 st.warning('Audio preview is text only. Actual speaker playback, network control, watchdog and physical I/O require confirmed hardware and on-site testing.')
 st.markdown('#### Site layout · agreed 8 October 2026')
 st.markdown('**Server Room (2nd floor):** BMAX B1 Plus Mini PC + Cogniser V1 processing unit')
 st.markdown('**LAN connection:** approximately 30 metres to Front of LAB (4th floor)')
 st.markdown('**Front of LAB:** 2 × Dahua IPC-HFW2441S-S (2.8 mm) CCTV, 1 × edge device (model not selected), 1 × speaker (model not selected), 1 × four-colour status indicator (model not selected)')
 st.caption('Camera 1: Face Recognition · Camera 2: PPE Detection. Edge device model and physical output interface are NOT confirmed.')

tabs=st.tabs(['LIVE OVERVIEW','FACE RECOGNITION','STEP 1 · TEMPERATURE + HYGIENE','STEP 2 · PPE','STEP 3 · HAND WASHING','STEP 4 · GLOVES','STEP 5 · METAL DETECTION','AUDIT & REPORT','COGNISER CONNECTION','4-COLOUR INDICATOR + AUDIO'])
@st.fragment(run_every="5s")
def live_overview():
 s=snapshot();a=s['active'];last=s['latest'];current=a or last
 state=(a['status'] if a else (last['status'] if last else 'WAITING'))
 color={'READY':'#ffffff','PASS':'#16a34a','FAIL':'#dc2626','WAITING':'#ffffff','PENDING':'#2563eb','INTERRUPTED':'#64748b'}.get(state,'#64748b')
 passed={c['key']:c['status'] for c in s['checks']}

 left,right=st.columns([1,3],gap='large')
 with left:
  st.markdown(f'<div class="tile" style="text-align:center"><div class="signal" style="background:{color};box-shadow:0 0 26px {color}66"></div><h2>{state}</h2><p>Legacy inspection state · see 4-colour tab</p><span class="tag">Lamp/speaker/gate not physically connected</span></div>',unsafe_allow_html=True)
 with right:
  st.subheader('Live Employee Inspection')
  with connect() as c:
   face_row_id=c.execute("SELECT payload FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
   face_employee=json.loads(face_row_id['payload']).get('employee_id','—') if face_row_id else '—'
   face_session=c.execute("SELECT id FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
   ppe_count=c.execute("SELECT COUNT(*) FROM attempts WHERE face_session_id=? AND source='COGNISER_PPE_DETECTION'",(face_session['id'],)).fetchone()[0] if face_session else 0
  x,y,z=st.columns(3);x.metric('Employee ID',face_employee);y.metric('Current Step',str(a['stage'])+'/5' if a and face_session and a['face_session_id']==face_session['id'] else '—');z.metric('PPE Attempts (current face)',ppe_count)
  st.info('Face Recognition identifies the worker and is never counted as an attempt. Every valid PPE detection adds one PPE attempt for that face session. Overall PENDING means other required checks are incomplete.')
 st.subheader('Original Factory Flow')
 columns=st.columns(5)
 for i,col in enumerate(columns,1):
  with col:st.markdown(f'<div class="tile"><b>STEP {i}</b><p>{STEP_NAMES[i-1]}</p><span class="tag">{len(STEPS[i])} checks</span></div>',unsafe_allow_html=True)
 st.subheader('Current Checkpoint Evidence')
 passed={c['key']:c['status'] for c in s['checks']}
 latest_observations=latest_ppe_component_results()
 for i in range(1,6):
  with st.expander(f'Step {i} · {STEP_NAMES[i-1]}',expanded=bool(a and a['stage']==i)):
   for k in STEPS[i]:
    observed=passed.get(k)
    if k in ('gloves','face_mask','hair_cover') and k in latest_observations:
     observed=latest_observations[k]+' · latest Cogniser PPE evidence'
    st.write(f'**{LABEL[k]}** — {observed or "PENDING · no confirmed sensor/operator result"}')
 st.divider()
 st.subheader('Live Cogniser Face Recognition · Camera 1')
 with connect() as c:
  face_row=c.execute("SELECT time,payload,note FROM events WHERE event='cogniser_face_raw' ORDER BY id DESC LIMIT 1").fetchone()
 if face_row:
  face_data=json.loads(face_row['payload'])
  f1,f2,f3,f4=st.columns(4)
  f1.metric('Employee ID',face_data.get('employee_id','—'))
  f2.metric('Camera',face_data.get('equipmentName') or '—')
  f3.metric('Match score',str(face_data.get('score','—')))
  f4.metric('Session created','YES' if face_data.get('accepted') else 'NO')
  st.caption(f"Received at {face_row['time']} (Asia/Bangkok) · Library: {face_data.get('faceLibName','—')} · {face_row['note']}")
  st.info('Face matching threshold must be validated with Cogniser. A score of 0.537 alone does not establish a factory-approved match threshold. The thermal field 0.001 is not used as body temperature.')
 else:st.info('Waiting for Cogniser Face Recognition JSON. Run TEST_FACE_SAMPLE.bat.')
 st.divider()
 st.subheader('Live Cogniser PPE Detection · Camera 2')
 with connect() as c:
  raw=c.execute("SELECT time,payload FROM events WHERE event='cogniser_ppe_raw' ORDER BY id DESC LIMIT 1").fetchone()
 if raw:
  data=json.loads(raw['payload']);rects=data.get('rectList',[])
  a1,a2,a3=st.columns(3)
  a1.metric('Camera',data.get('equipmentName') or '—')
  a2.metric('PPE detections / attempts',len([r for r in rects if len(str(r.get('value','')).split('-'))==3 and all(v in ('0','1') for v in str(r.get('value','')).split('-'))]))
  a3.metric('Linked employee',data.get('employee_id') or '—')
  st.caption(f"Received at {raw['time']} (Asia/Bangkok) · Task: {data.get('taskName','—')}")
  if rects:
   st.dataframe(pd.DataFrame([{'Object ID':r.get('id'),'Cogniser raw value':r.get('value'),'Employee ID (sequence)':data.get('employee_id') or '—'} for r in rects]),use_container_width=True,hide_index=True)
  st.info(f'Latest PPE message: {len(rects)} rectangles. Each valid rectangle = ONE attempt, so the supplied four-valid-rectangle sample produces FOUR attempts. Mapping: glove-mask-hat; 1 = worn, 0 = not worn.')
 else:st.info('Waiting for Cogniser PPE JSON. Run TEST_PPE_SAMPLE.bat to display a sample detection.')
 st.caption('Auto-refresh every 5 seconds. No physical gate-open commands are issued.')


def show_decoded_ppe(data, component=None):
 rects=data.get('rectList') or []
 st.markdown('#### Individual PPE Detection · 1 = WORN / 0 = NOT WORN')
 valid=[]
 for idx,r in enumerate(rects,1):
  bits=str(r.get('value','')).strip().split('-')
  if len(bits)!=3 or any(v not in ('0','1') for v in bits):
   st.warning(f'Detection {idx}: unrecognized PPE code {r.get("value")}');continue
  valid.append(bits)
  st.markdown(f'**Detection {idx} · Employee {data.get("employee_id") or "Not linked"}**')
  selected=[(name,bit) for name,bit in zip(('Gloves','Face Mask','Hair Cover'),bits) if component is None or name in component]
  cols=st.columns(len(selected))
  for col,(name,bit) in zip(cols,selected):
   with col:
    color='#15803d' if bit=='1' else '#b91c1c'
    bg='#f0fdf4' if bit=='1' else '#fef2f2'
    status='PASS · WORN' if bit=='1' else 'FAIL · NOT WORN'
    st.markdown(f'<div style="background:{bg};border:2px solid {color};border-radius:12px;padding:16px;text-align:center"><b>{name}</b><h2 style="color:{color};margin:6px 0">{bit}</h2><b style="color:{color}">{status}</b></div>',unsafe_allow_html=True)
 if valid:
  st.markdown('#### Latest detection summary (last valid detection entry)')
  selected=[(j,name) for j,name in enumerate(('Gloves','Face Mask','Hair Cover')) if component is None or name in component]
  cols=st.columns(len(selected))
  for col,(j,name) in zip(cols,selected):
   col.metric(name,'PASS' if valid[-1][j]=='1' else 'FAIL')
  st.caption('Uses the last valid detection entry, not the worst result across all entries. If rectangles represent different people, this is NOT a verified identity match; validate the Cogniser event order and one-person-at-a-time operation before live gate use.')
 else:st.warning('No valid glove-mask-hat values found.')

@st.fragment(run_every="5s")
def cogniser_checkpoint_live(step):
 st.subheader('Live Cogniser evidence · automatic refresh (5 seconds)')
 with connect() as c:
  face=c.execute("SELECT time,payload,note FROM events WHERE event='cogniser_face_raw' ORDER BY id DESC LIMIT 1").fetchone()
  ppe=c.execute("SELECT time,payload,note FROM events WHERE event='cogniser_ppe_raw' ORDER BY id DESC LIMIT 1").fetchone()
 if step==0:
  if not face:st.info('No face JSON received yet. Run TEST_FACE_SAMPLE.bat or configure Cogniser LAN push.');return
  d=json.loads(face['payload']);x,y,z=st.columns(3)
  x.metric('Employee ID',d.get('employee_id') or '—');y.metric('Camera',d.get('equipmentName') or '—');z.metric('Match score',str(d.get('score','—')))
  st.caption(f"Received: {face['time']} · Library: {d.get('faceLibName')} · Session accepted: {d.get('accepted')}")
  st.warning('Score threshold requires Cogniser validation. A received face event is not proof of an approved match threshold.')
 elif step in (2,4):
  if not ppe:st.info('No PPE JSON received yet. Run TEST_PPE_SAMPLE.bat or configure Cogniser LAN push.');return
  d=json.loads(ppe['payload']);rows=d.get('rectList') or []
  with connect() as c:
   face_row_id=c.execute("SELECT payload FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
   face_employee=json.loads(face_row_id['payload']).get('employee_id','—') if face_row_id else '—'
   face_session=c.execute("SELECT id FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
   ppe_count=c.execute("SELECT COUNT(*) FROM attempts WHERE face_session_id=? AND source='COGNISER_PPE_DETECTION'",(face_session['id'],)).fetchone()[0] if face_session else 0
  x,y,z=st.columns(3);x.metric('Camera',d.get('equipmentName') or '—');y.metric('PPE detections / attempts',len([r for r in rows if len(str(r.get('value','')).split('-'))==3 and all(v in ('0','1') for v in str(r.get('value','')).split('-'))]));z.metric('Linked employee',d.get('employee_id') or '—')
  st.caption(f"Received: {ppe['time']} · {d.get('taskName','')} · Source event stored")
  show_decoded_ppe(d, ('Face Mask','Hair Cover') if step==2 else ('Gloves',))
  with st.expander('Raw Cogniser codes (technical reference)'):
   st.dataframe(pd.DataFrame([{'Person / object':r.get('id'),'Raw glove-mask-hat code':r.get('value'),'Linked Employee ID':d.get('employee_id') or '—'} for r in rows]),hide_index=True,use_container_width=True)
  if step==2:st.info('Face mask and hair cover are decoded automatically at Step 2. Clothing and shoes still require a separate trained model or confirmed inspection event.')
  else:st.info('Glove status is read from the latest PPE event automatically. Each valid PPE rectangle creates a new audit attempt.')
  st.info('The individual component result can be PASS/FAIL even while the overall inspection is PENDING due to other missing mandatory checks. 1 = worn, 0 = not worn. Latest Face Recognition determines employee. The most recent valid detection entry supplies the latest component result. Identity and event ordering require factory validation.')
 else:st.info('This checkpoint requires a separate sensor, validated AI model, or operator confirmation. The provided Face/PPE JSON does not contain its result.')

with tabs[0]:
 live_overview()
with tabs[1]:
 st.header('Face Recognition · Camera Identity Layer');st.write('Cogniser sends the complete facecompare JSON. The receiver extracts strRes.peopleName and creates a session if no other attempt is active.');st.code('POST http://MINI_PC_IP:8022/api/cogniser/face\nGET http://MINI_PC_IP:8022/api/cogniser/face/latest',language='http');st.info('Use TEST_FACE_SAMPLE.bat to simulate Employee ID 593037. Match threshold must be validated with Cogniser.')
 cogniser_checkpoint_live(0)
@st.fragment(run_every="5s")
def live_checkpoint(i):
 st.header(f'Step {i} · {STEP_NAMES[i-1]}')
 st.caption('Confirmed incoming Cogniser / sensor events are stored by the backend. Manual checks require operator confirmation or validated AI.')
 confirmed={c['key']:c['status'] for c in snapshot()['checks']}
 detected=latest_ppe_component_results()
 for key in STEPS[i]:
  label=LABEL[key]
  typ='AI MODEL TRAINING PROPOSED' if key in ORANGE else ('MANUAL / FACTORY CONFIRMATION' if key in MANUAL else ('THERMAL SENSOR' if key=='temperature' else ('METAL DETECTOR' if key=='mobile_phone' else 'COGNISER DETECTION')))
  st.markdown(f'**{label}** · `{typ}`')
  display=detected.get(key) if key in ('hair_cover','face_mask','gloves') else confirmed.get(key)
  st.write('Status: **'+(f'{display} · CONFIRMED COGNISER DETECTION' if key in detected else (display or 'PENDING · NO CONFIRMED RESULT FOR THIS FACE SESSION'))+'**')
 if i in (2,4):st.caption('Receiver diagnostic: '+face_ppe_diagnostics())
 cogniser_checkpoint_live(i)
 st.divider()
 st.write('Overall status stays PENDING until all required checks are confirmed. Individual PPE PASS/FAIL appears immediately.')
for i,tab in enumerate(tabs[2:7],1):
 with tab:live_checkpoint(i)
with tabs[7]:
 st.header('Monthly Audit · All Attempts')
 st.caption('One valid PPE detection = one PPE attempt. Numbering restarts at 1 for each Face Recognition. Individual PASS/FAIL is separate from overall PENDING.')
 with connect() as c:
  df=pd.read_sql_query("""SELECT ROW_NUMBER() OVER(PARTITION BY face_session_id ORDER BY id) AS ppe_attempt, employee_id,started,finished,stage,status,reason,source,id AS internal_id FROM attempts WHERE source='COGNISER_PPE_DETECTION' ORDER BY id DESC""",c)
  events=pd.read_sql_query('SELECT time,event,accepted,note FROM events ORDER BY id DESC LIMIT 100',c)
 st.dataframe(df.drop(columns=['internal_id']),use_container_width=True,hide_index=True)
 st.subheader('Attempt details · Employee ID / PASS / FAIL / PENDING')
 st.caption('PPE attempt numbering starts at 1 for each accepted Face Recognition. Face Recognition is not an attempt. Internal database identifiers are not shown.')
 with connect() as c:
  details=pd.read_sql_query('SELECT attempt_id,key,status,time FROM checks ORDER BY attempt_id,key',c)
 for _,attempt in df.iterrows():
  aid=int(attempt['internal_id']);number=int(attempt['ppe_attempt']);emp=str(attempt['employee_id'])
  recorded=details[details['attempt_id']==aid]
  observed={str(r['key']):str(r['status']) for _,r in recorded.iterrows()}
  n_pass=sum(v=='PASS' for v in observed.values());n_fail=sum(v=='FAIL' for v in observed.values())
  n_pending=sum(k not in observed for keys in STEPS.values() for k in keys)
  with st.expander(f'PPE Attempt {number} · Employee ID {emp} · {attempt["status"]} · PASS {n_pass} / FAIL {n_fail} / PENDING {n_pending}',expanded=(aid==int(df.iloc[0]['internal_id']))):
   rows=[]
   for step,keys in STEPS.items():
    for key in keys:
     rows.append({'Checkpoint':f'Step {step}', 'Detected / inspection type':LABEL[key], 'Result':observed.get(key,'PENDING'), 'Data received':'YES' if key in observed else 'NO'})
   st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
   st.caption('PASS/FAIL here refers to individual checks. Overall PENDING means some mandatory checks are still missing. Each valid PPE rectangle is one inspection attempt.')
 st.download_button('Download Audit CSV',df.drop(columns=['internal_id']).to_csv(index=False).encode('utf-8-sig'),'cogniser_original_flow_audit.csv','text/csv')
 st.subheader('Recent Incoming Events');st.caption('Events count inbound messages; a single PPE message can contain multiple independent PPE attempts.');st.dataframe(events,use_container_width=True,hide_index=True)
 st.subheader('Factory Form · Monthly Audit · Word Report')
 from reporting import monthly,factory_pdf,word_report,summary,ollama_report
 from datetime import datetime
 month=st.text_input('Report month (YYYY-MM)',datetime.now().strftime('%Y-%m'),key='report_month_audit')
 try:
  report_df,report_checks=monthly(month)
  st.write('Monthly summary:',summary(report_df))
  st.download_button('Download Factory Form PDF',factory_pdf(month,report_df),f'FACTORY_FORM_{month}.pdf',mime='application/pdf')
  st.download_button('Download Monthly Word Report',word_report(month,report_df,report_checks),f'COGNISER_MONTHLY_REPORT_{month}.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
  st.caption('Factory form: latest completed PASS/FAIL per employee per day. Pending observations do not overwrite completed results. QA approval required before official factory use.')
  st.caption('LLM report uses Ollama separately; AI analysis is not a substitute for confirmed inspection evidence.')
 except Exception as exc:st.error(f'Report generation: {exc}')
 st.warning('This prototype does not claim ISO certification or physical gate control.')
with tabs[8]:
 st.header('LAN Data Receiver · Integration Guide')
 st.success('FastAPI receiver: POST /api/cogniser/face, /api/cogniser/ppe, and confirmed /api/events/...')
 st.code('POST /api/events/temperature\n{"value":36.7,"source":"THERMAL_SENSOR"}\n\nPOST /api/events/check\n{"key":"hair_cover","result":"PASS","source":"COGNISER"}',language='http')
 st.code('POST http://MINI_PC_IP:8022/api/cogniser/ppe\nGET http://MINI_PC_IP:8022/api/cogniser/ppe/latest',language='http')
 st.write('Cogniser must be configured to transmit to the Mini PC IP address, and its actual JSON format must be mapped to these event fields. This receiver does not magically interpret unknown vendor messages.')
 st.write('Step 1: temperature, ear_ring, necklace, bracelet, ring, nail, wound, plaster. Step 2: hair_cover, face_mask, protective_clothing, shoes. Step 3: hand_washing. Step 4: gloves. Step 5: mobile_phone.')
 st.warning('Gate Open is virtual eligibility only. Never connect a physical gate before hardware interlocks, fail-safe controls and QA sign-off.')

with tabs[8]:
 st.subheader('Raw Cogniser JSON testing')
 st.write('POST `/api/cogniser/face` to set the latest employee. POST `/api/cogniser/ppe` to decode glove-mask-hat (1 worn / 0 absent). Automatic decisions are limited to the active checkpoint. Physical gate is not connected.')

# v28: original-flow monthly factory form, full audit and optional SOP-grounded LLM
from reporting import monthly,summary,factory_pdf,word_report,ollama_report,SOP
with tabs[7]:
 st.divider()
 st.subheader('Factory Form FM-PD-01-01 · Monthly Audit · LLM Report')
 month=st.text_input('Reporting month (YYYY-MM)',value=__import__('datetime').datetime.now().strftime('%Y-%m'),key='report_month')
 try:
  mdf,mchecks=monthly(month);tot=summary(mdf)
  c1,c2,c3,c4=st.columns(4)
  c1.metric('Attempts',tot['attempts']);c2.metric('PASS',tot['pass']);c3.metric('FAIL',tot['fail']);c4.metric('PENDING',tot['pending'])
  st.caption('Factory Form follows the original two-half-month reference layout and uses the latest COMPLETED PASS/FAIL per employee per day. PENDING never overwrites completed results. All attempts remain in Monthly Audit.')
  st.download_button('Download Factory Form FM-PD-01-01 (PDF)',data=factory_pdf(month,mdf),file_name=f'FM-PD-01-01_{month}.pdf',mime='application/pdf')
  st.download_button('Download Monthly Audit (CSV)',data=mdf.to_csv(index=False).encode('utf-8-sig'),file_name=f'MONTHLY_AUDIT_{month}.csv',mime='text/csv')
  st.markdown('**Factory SOP reference: SD-PD-01-01**')
  for ref,rule in SOP:st.caption(f'{ref}: {rule}')
  model=st.text_input('Local Ollama model',value='llama3.2:1b',key='v28_model')
  if 'v28_ai' not in st.session_state:st.session_state.v28_ai={}
  if st.button('Generate AI Analysis (Ollama)',key='v28_gen'):
   try:
    with st.spinner('Analysing recorded monthly data...'):
     st.session_state.v28_ai[month]=ollama_report(month,mdf,model)
   except Exception as exc:st.error(f'Ollama unavailable: {exc}. You can still export a deterministic Word report.')
  analysis=st.session_state.v28_ai.get(month,'')
  if analysis:st.text_area('AI Analysis',analysis,height=250)
  st.download_button('Download Professional Monthly Report (Word)',data=word_report(month,mdf,mchecks,analysis),file_name=f'COGNISER_MONTHLY_REPORT_{month}.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
  st.info('ISO / factory QA approval is not implied. Physical gate, sensors and vendor PPE person-matching still require commissioning.')
 except Exception as exc:st.error(f'Report error: {exc}')

with tabs[9]:
 hardware_simulation()
