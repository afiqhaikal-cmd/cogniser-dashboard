
from datetime import datetime, timezone, timedelta
def malaysia_time(value):
 try:
  dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
  if dt.tzinfo is None: return str(value)+' (timezone unspecified)'
  return dt.astimezone(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
 except (ValueError,TypeError): return str(value)
import streamlit as st,pandas as pd,sqlite3
from core import connect,snapshot,STEPS,LABEL,ORANGE,MANUAL
import json
STEP_NAMES=['Temperature + Jewellery / Nail / Wound / Plaster','Hair Cover / Mask / Clothing / Shoes','Hand Washing','Gloves','Mobile Phone / Metal Detection']
st.set_page_config(page_title='FOOD SAFETY MONITORING-ISO22000',layout='wide',page_icon='🏭')
st.markdown('''<style>.block-container{max-width:1450px;padding-top:1.4rem}.hero{background:linear-gradient(100deg,#092f50,#086b83);color:white;border-radius:18px;padding:26px}.hero h1{color:white;margin:0}.hero p{color:#d5edf4;margin:6px 0 0}.tile{border:1px solid #cbd5e1;border-radius:12px;padding:16px;min-height:145px;background:#f8fafc}.tag{font-size:12px;color:#64748b}.signal{width:110px;height:110px;border-radius:100%;margin:12px auto;border:6px solid white;box-shadow:0 0 24px #9ca3af}</style>''',unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>FOOD SAFETY MONITORING-ISO22000</h1><p>Face Recognition → Step 1 → Step 2 → Step 3 → Step 4 → Step 5 → Gate Eligibility</p></div>',unsafe_allow_html=True)
st.caption('DATA REFRESH · 5 SECONDS | Inspection status is based on recorded and verified events.')
s=snapshot();a=s['active'];last=s['latest'];current=a or last;state=(a['status'] if a else (last['status'] if last else 'WAITING'));color={'READY':'#ffffff','PASS':'#16a34a','FAIL':'#dc2626','WAITING':'#ffffff','PENDING':'#2563eb','INTERRUPTED':'#64748b'}.get(state,'#64748b')
def latest_ppe_component_results():
 """Only show confirmed persisted checks for the current checkpoint."""
 snap=snapshot()
 return {r['key']:r['status'] for r in snap['checks'] if r['key'] in ('gloves','face_mask','hair_cover')}

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
  count=c.execute("SELECT COUNT(*) FROM attempts WHERE face_session_id=? AND source='CLOUD_FACE_CHECKPOINT'",(face['id'],)).fetchone()[0] if face else 0
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
 st.subheader('Status Indicator · Operational Overview')
 st.caption('WHITE · Ready | BLUE · Processing | GREEN · Passed | RED · Failed. Physical indicator connection pending commissioning.')
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
 c.metric('Checkpoint sessions · current face',count)
 st.info('Audio status: '+audio)
 st.caption('External speaker connection: pending commissioning.')
 st.markdown('#### Site layout · agreed 8 October 2026')
 st.markdown('**Server Room (2nd floor):** BMAX B1 Plus Mini PC + Cogniser V1 processing unit')
 st.markdown('**LAN connection:** approximately 30 metres to Front of LAB (4th floor)')
 st.markdown('**Front of LAB:** 1 × shared checkpoint camera (physical configuration to verify), 1 × edge device (model not selected), 1 × speaker (model not selected), 1 × four-colour status indicator (model not selected)')
 st.caption('One shared checkpoint camera · Face Recognition + PPE Detection (separate JSON) · Pending commissioning')

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
   ppe_count=c.execute("SELECT COUNT(*) FROM attempts WHERE face_session_id=? AND source='CLOUD_FACE_CHECKPOINT'",(face_session['id'],)).fetchone()[0] if face_session else 0
  x,y,z=st.columns(3);x.metric('Employee ID',face_employee);y.metric('Current Step',str(a['stage'])+'/5' if a and face_session and a['face_session_id']==face_session['id'] else '—');z.metric('Checkpoint sessions (current face)',ppe_count)
  st.info('One accepted face event creates one checkpoint session. PPE rectangles are evidence within that session, not separate attempts. Overall PENDING means required checks remain unverified.')
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
 st.subheader('Live Cogniser Face Recognition · Shared Camera')
 with connect() as c:
  face_row=c.execute("SELECT id,time,payload,accepted,note FROM events WHERE event='cogniser_face_raw' ORDER BY id DESC LIMIT 1").fetchone()
 if face_row:
  face_data=json.loads(face_row['payload'])
  f1,f2,f3,f4=st.columns(4)
  f1.metric('Employee ID',face_data.get('employee_id','—'))
  f2.metric('Camera',face_data.get('equipmentId') or face_data.get('equipmentName') or '—')
  f3.metric('Match score',str(face_data.get('score','—')))
  
  with connect() as session_conn:
   session_exists=bool(session_conn.execute('SELECT 1 FROM attempts WHERE face_session_id=? LIMIT 1',(face_row['id'],)).fetchone())
  f4.metric('Session created','YES' if face_row['accepted'] and session_exists else 'NO')
  st.caption(f"Received at {malaysia_time(face_row['time'])} (Malaysia time) · Library: {face_data.get('faceLibName','—')} · {face_row['note']}")
  st.info('Face matching threshold pending validation. Device thermal metadata is not treated as body temperature.')
 else:st.info('Awaiting Face Recognition event.')
 st.divider()
 st.subheader('Live Cogniser PPE Detection · Shared Camera')
 with connect() as c:
  raw=c.execute("SELECT time,payload FROM events WHERE event='cogniser_ppe_raw' ORDER BY id DESC LIMIT 1").fetchone()
 if raw:
  data=json.loads(raw['payload']);rects=data.get('rectList',[])
  a1,a2,a3=st.columns(3)
  a1.metric('Camera',data.get('equipmentId') or data.get('equipmentName') or '—')
  a2.metric('PPE alarm rectangles',len([r for r in rects if len(str(r.get('value','')).split('-'))==3 and all(v in ('0','1') for v in str(r.get('value','')).split('-'))]))
  a3.metric('Linked employee',data.get('employee_id') or '—')
  st.caption(f"Received at {malaysia_time(raw['time'])} (Malaysia time) · Task: {data.get('taskName','—')}")
  if rects:
   st.dataframe(pd.DataFrame([{'Object ID':r.get('id'),'Cogniser raw value':r.get('value'),'Employee ID (sequence)':data.get('employee_id') or '—'} for r in rects]),use_container_width=True,hide_index=True)
  st.info(f'Latest PPE message: {len(rects)} rectangles. Rectangles are observations, not separate employee attempts. Device bit mapping requires vendor confirmation.')
 else:st.info('Awaiting PPE Detection event.')
 st.caption('Refresh interval: 5 seconds | Access-control output: Not configured')


def show_decoded_ppe(data, component=None):
 """Raw evidence only: PPE bit order and meaning are not vendor-verified."""
 rects=data.get('rectList') or []
 st.markdown('#### PPE alarm evidence · unverified device codes')
 st.warning('Cogniser PPE bit positions and 0/1 semantics have NOT been confirmed by the vendor. No PASS/FAIL is inferred from these raw codes.')
 if rects:
  st.dataframe(pd.DataFrame([{'Rectangle':i,'Object ID':r.get('id'),'Raw code':r.get('value')} for i,r in enumerate(rects,1)]),hide_index=True,use_container_width=True)
 else:
  st.info('No PPE rectangles recorded.')

@st.fragment(run_every="5s")
def cogniser_checkpoint_live(step):
 st.subheader('Live Cogniser evidence · automatic refresh (5 seconds)')
 with connect() as c:
  face=c.execute("SELECT id,time,payload,accepted,note FROM events WHERE event='cogniser_face_raw' ORDER BY id DESC LIMIT 1").fetchone()
  ppe=c.execute("SELECT time,payload,note FROM events WHERE event='cogniser_ppe_raw' ORDER BY id DESC LIMIT 1").fetchone()
 if step==0:
  if not face:st.info('No Face Recognition event received.');return
  d=json.loads(face['payload']);x,y,z=st.columns(3)
  x.metric('Employee ID',d.get('employee_id') or '—');y.metric('Camera',d.get('equipmentId') or d.get('equipmentName') or '—');z.metric('Match score',str(d.get('score','—')))
  st.caption(f"Received: {face['time']} · Library: {d.get('faceLibName')} · Session accepted: {d.get('accepted')}")
  st.warning('Identity acceptance threshold pending device validation.')
 elif step in (2,4):
  if not ppe:st.info('No PPE Detection event received.');return
  d=json.loads(ppe['payload']);rows=d.get('rectList') or []
  with connect() as c:
   face_row_id=c.execute("SELECT payload FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
   face_employee=json.loads(face_row_id['payload']).get('employee_id','—') if face_row_id else '—'
   face_session=c.execute("SELECT id FROM events WHERE event='cogniser_face_raw' AND accepted=1 ORDER BY id DESC LIMIT 1").fetchone()
   ppe_count=c.execute("SELECT COUNT(*) FROM attempts WHERE face_session_id=? AND source='CLOUD_FACE_CHECKPOINT'",(face_session['id'],)).fetchone()[0] if face_session else 0
  x,y,z=st.columns(3);x.metric('Camera',d.get('equipmentId') or d.get('equipmentName') or '—');y.metric('PPE alarm rectangles',len([r for r in rows if len(str(r.get('value','')).split('-'))==3 and all(v in ('0','1') for v in str(r.get('value','')).split('-'))]));z.metric('Linked employee',d.get('employee_id') or '—')
  st.caption(f"Received: {ppe['time']} · {d.get('taskName','')} · Source event stored")
  show_decoded_ppe(d, ('Face Mask','Hair Cover') if step==2 else ('Gloves',))
  with st.expander('Raw Cogniser codes (technical reference)'):
   st.dataframe(pd.DataFrame([{'Person / object':r.get('id'),'Raw glove-mask-hat code':r.get('value'),'Linked Employee ID':d.get('employee_id') or '—'} for r in rows]),hide_index=True,use_container_width=True)
  if step==2:st.info('Mask and hair-cover codes are displayed as raw evidence until vendor mapping is verified. Clothing and shoes require separate validated checks.')
  else:st.info('Glove alarm evidence is displayed without automatically creating another inspection attempt.')
  st.info('PPE raw codes do not establish PASS or FAIL. One-person, same-camera and timestamp association must be verified at the factory.')
 else:st.info('This checkpoint requires an approved sensor or operator verification. No confirmed result is currently recorded.')

with tabs[0]:
 live_overview()
with tabs[1]:
 st.header('Face Recognition · Shared Checkpoint Camera');st.write('Employee identification records received from the shared camera are displayed below.');st.info('Identity matching must meet approved factory acceptance criteria.')
 cogniser_checkpoint_live(0)
@st.fragment(run_every="5s")
def live_checkpoint(i):
 st.header(f'Step {i} · {STEP_NAMES[i-1]}')
 st.caption('Confirmed incoming Cogniser / sensor events are stored by the backend. Manual checks require operator confirmation or validated AI.')
 confirmed={c['key']:c['status'] for c in snapshot()['checks']}
 detected=latest_ppe_component_results()
 for key in STEPS[i]:
  label=LABEL[key]
  typ='REQUIRES VERIFIED DETECTION METHOD' if key in ORANGE else ('MANUAL / FACTORY CONFIRMATION' if key in MANUAL else ('THERMAL SENSOR' if key=='temperature' else ('METAL DETECTOR' if key=='mobile_phone' else 'COGNISER DETECTION')))
  st.markdown(f'**{label}** · `{typ}`')
  display=detected.get(key) if key in ('hair_cover','face_mask','gloves') else confirmed.get(key)
  st.write('Status: **'+(f'{display} · PERSISTED CHECK EVIDENCE' if key in detected else (display or 'PENDING · NO CONFIRMED RESULT FOR THIS FACE SESSION'))+'**')
 if i in (2,4):st.caption('Receiver diagnostic: '+face_ppe_diagnostics())
 cogniser_checkpoint_live(i)
 st.divider()
 st.write('Overall status stays PENDING until all required checks are confirmed. Individual PPE PASS/FAIL appears immediately.')
for i,tab in enumerate(tabs[2:7],1):
 with tab:live_checkpoint(i)
with tabs[7]:
 st.header('Monthly Audit · All Checkpoint Sessions')
 st.caption('One accepted face check-in creates one checkpoint session. PPE rectangles are evidence, not extra sessions.')
 with connect() as c:
  df=pd.read_sql_query("SELECT id AS attempt_id,employee_id,started,finished,stage,status,reason,source FROM attempts ORDER BY id DESC",c)
  events=pd.read_sql_query('SELECT time,event,accepted,note FROM events ORDER BY id DESC LIMIT 100',c)
 st.dataframe(df,use_container_width=True,hide_index=True)
 st.subheader('Checkpoint details · confirmed checks')
 with connect() as c:
  details=pd.read_sql_query('SELECT attempt_id,key,status,time FROM checks ORDER BY attempt_id,key',c)
 for _,attempt in df.iterrows():
  aid=int(attempt['attempt_id']);emp=str(attempt['employee_id'])
  recorded=details[details['attempt_id']==aid]
  observed={str(r['key']):str(r['status']) for _,r in recorded.iterrows()}
  n_pass=sum(v=='PASS' for v in observed.values());n_fail=sum(v=='FAIL' for v in observed.values())
  n_pending=sum(k not in observed for keys in STEPS.values() for k in keys)
  with st.expander(f'Checkpoint {aid} · Employee {emp} · {attempt["status"]} · PASS {n_pass} / FAIL {n_fail} / PENDING {n_pending}'):
   rows=[{'Step':step,'Check':LABEL[key],'Result':observed.get(key,'PENDING'),'Confirmed evidence': 'YES' if key in observed else 'NO'} for step,keys in STEPS.items() for key in keys]
   st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
 st.download_button('Download Audit CSV',df.to_csv(index=False).encode('utf-8-sig'),'cogniser_checkpoint_audit.csv','text/csv')
 st.subheader('Recent Incoming Events')
 st.caption('Events count inbound messages, not individual rectangles.')
 st.dataframe(events,use_container_width=True,hide_index=True)
 with connect() as cloud_conn:
  exists=cloud_conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cloud_evidence'").fetchone()
  if exists:
   cloud_df=pd.read_sql_query('SELECT event_time,event_type,employee_id,camera_id,accepted,payload FROM cloud_evidence ORDER BY event_time DESC',cloud_conn)
   st.subheader('Supabase Cloud Evidence · Face / PPE / Manual / Other')
   st.caption('Cloud records are read-only evidence. Association and all mandatory checks require verification.')
   st.dataframe(cloud_df,use_container_width=True,hide_index=True)
   st.download_button('Download Cloud Evidence CSV',cloud_df.to_csv(index=False).encode('utf-8-sig'),'cogniser_cloud_evidence.csv','text/csv')

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
  st.caption('Review commentary does not replace verified inspection records.')
 except Exception as exc:st.error(f'Report generation: {exc}')
 st.warning('Inspection records support internal food safety monitoring; certification status and physical access control are managed separately.')
with tabs[8]:
 st.header('Cogniser Data Interface · Connection Status')
 st.success('FastAPI receiver: POST /api/cogniser/face, /api/cogniser/ppe, and confirmed /api/events/...')
 st.code('POST /api/events/temperature\n{"value":36.7,"source":"THERMAL_SENSOR"}\n\nPOST /api/events/check\n{"key":"hair_cover","result":"PASS","source":"COGNISER"}',language='http')
 st.code('POST http://MINI_PC_IP:8022/api/cogniser/ppe\nGET http://MINI_PC_IP:8022/api/cogniser/ppe/latest',language='http')
 st.write('Integration status: Device interface verification pending.')
 st.write('Step 1: temperature, ear_ring, necklace, bracelet, ring, nail, wound, plaster. Step 2: hair_cover, face_mask, protective_clothing, shoes. Step 3: hand_washing. Step 4: gloves. Step 5: mobile_phone.')
 st.warning('Access eligibility is informational. Physical access-control integration is not enabled.')

with tabs[8]:
 st.subheader('Cogniser Interface Status')
 st.write('Face Recognition and PPE Detection event interfaces. Inspection results remain subject to approved verification and access-control procedures.')

# v28: original-flow monthly factory form, full audit and optional SOP-grounded LLM
from reporting import monthly,summary,factory_pdf,word_report,ollama_report,SOP
with tabs[7]:
 st.divider()
 st.subheader('Factory Form FM-PD-01-01 · Monthly Audit · Compliance Review')
 month=st.text_input('Reporting month (YYYY-MM)',value=__import__('datetime').datetime.now().strftime('%Y-%m'),key='report_month')
 try:
  mdf,mchecks=monthly(month);tot=summary(mdf)
  c1,c2,c3,c4=st.columns(4)
  c1.metric('Attempts',tot['attempts']);c2.metric('PASS',tot['pass']);c3.metric('FAIL',tot['fail']);c4.metric('PENDING',tot['pending'])
  st.caption('Monthly form uses the latest completed PASS/FAIL per employee per day. Incomplete records remain PENDING and are retained in the audit history.')
  st.download_button('Download Factory Form FM-PD-01-01 (PDF)',data=factory_pdf(month,mdf),file_name=f'FM-PD-01-01_{month}.pdf',mime='application/pdf')
  st.download_button('Download Monthly Audit (CSV)',data=mdf.to_csv(index=False).encode('utf-8-sig'),file_name=f'MONTHLY_AUDIT_{month}.csv',mime='text/csv')
  st.markdown('**Reference framework: ISO 22000:2018 and ISO 22002-100:2025, Clause 14**')
  for ref,rule in SOP:st.caption(f'{ref}: {rule}')
  model=st.text_input('Analysis Engine',value='llama3.2:1b',key='v28_model')
  if 'v28_ai' not in st.session_state:st.session_state.v28_ai={}
  if st.button('Generate Compliance Review',key='v28_gen'):
   try:
    with st.spinner('Analysing recorded monthly data...'):
     st.session_state.v28_ai[month]=ollama_report(month,mdf,model)
   except Exception as exc:st.error('Compliance review service unavailable. The standard report remains available.')
  analysis=st.session_state.v28_ai.get(month,'')
  if analysis:st.text_area('Compliance Review',analysis,height=250)
  st.download_button('Download Professional Monthly Report (Word)',data=word_report(month,mdf,mchecks,analysis),file_name=f'COGNISER_MONTHLY_REPORT_{month}.docx',mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
  st.info('Compliance review requires authorized QA verification. Device and access-control integration status must be confirmed separately.')
 except Exception as exc:st.error(f'Report error: {exc}')

with tabs[9]:
 hardware_simulation()

# Local-only data management. Never delete cloud evidence from an online dashboard.
if not (__import__('os').environ.get('COGNISER_ONLINE') or __import__('os').environ.get('STREAMLIT_SHARING_MODE')):
 with st.sidebar.expander('DATA MANAGEMENT · LOCAL ONLY'):
  st.warning('This deletes local events and attempts only. Online Supabase records are NOT deleted. A backup is created first.')
  confirm=st.checkbox('I understand: delete all LOCAL inspection records',key='local_reset_confirm')
  if st.button('DELETE ALL LOCAL DATA',disabled=not confirm,type='secondary'):
   from local_admin import reset_local
   try:
    st.success(reset_local())
    st.rerun()
   except Exception as exc: st.error(f'Reset failed; no claim of success: {exc}')
