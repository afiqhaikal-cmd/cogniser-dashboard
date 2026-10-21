import sqlite3,os,datetime,json
DB=os.path.join(os.path.dirname(__file__),'inspection.sqlite3')
STEPS={1:['temperature','ear_ring','necklace','bracelet','ring','nail','wound','plaster'],2:['hair_cover','face_mask','protective_clothing','shoes'],3:['hand_washing'],4:['gloves'],5:['mobile_phone']}
LABEL={'temperature':'Temperature (36.0–37.5 °C)','ear_ring':'Ear Ring','necklace':'Necklace','bracelet':'Bracelet','ring':'Ring','nail':'Nail','wound':'Wound','plaster':'Plaster','hair_cover':'Hair Cover','face_mask':'Face Mask','protective_clothing':'Protective Clothing','shoes':'Shoes','hand_washing':'Hand Washing','gloves':'Gloves','mobile_phone':'Mobile Phone / Metal Detection'}
ORANGE={'temperature','plaster','protective_clothing','shoes'}
MANUAL={'ear_ring','necklace','bracelet','ring','nail','wound','plaster','hand_washing'}
def time():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7))).isoformat(timespec='seconds')
def connect():
 c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS attempts (id INTEGER PRIMARY KEY AUTOINCREMENT,employee_id TEXT,started TEXT,finished TEXT,stage INTEGER DEFAULT 1,status TEXT DEFAULT "PENDING",reason TEXT DEFAULT "",source TEXT DEFAULT "COGNISER")');c.execute('CREATE TABLE IF NOT EXISTS checks (attempt_id INTEGER,key TEXT,status TEXT,source TEXT,time TEXT,PRIMARY KEY(attempt_id,key))');c.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT,time TEXT,event TEXT,payload TEXT,accepted INTEGER,note TEXT)');
 if 'face_session_id' not in [r[1] for r in c.execute('PRAGMA table_info(attempts)')]:c.execute('ALTER TABLE attempts ADD COLUMN face_session_id INTEGER');
 return c
ALL_KEYS=[key for group in STEPS.values() for key in group]
def active(c):
 return c.execute("SELECT * FROM attempts WHERE status='PENDING' AND finished IS NULL ORDER BY id DESC LIMIT 1").fetchone()
def recalculate(c,attempt_id):
 rows=c.execute('SELECT key,status FROM checks WHERE attempt_id=?',(attempt_id,)).fetchall()
 observed={r['key']:r['status'] for r in rows}
 missing=[k for k in ALL_KEYS if k not in observed]
 stage=next((i for i,keys in STEPS.items() if any(k not in observed for k in keys)),6)
 if missing:
  status='PENDING';reason='Awaiting: '+', '.join(missing);finished=None
 else:
  failures=[k for k,v in observed.items() if v=='FAIL']
  status='FAIL' if failures else 'PASS'
  reason='Failed checks: '+', '.join(failures) if failures else 'All mandatory checks passed'
  finished=time()
 c.execute('UPDATE attempts SET stage=?,status=?,reason=?,finished=? WHERE id=?',(stage,status,reason,finished,attempt_id))
 return status

def event(kind,payload):
 if kind not in ('face','temperature','check'):raise ValueError('Unsupported event type')
 if not isinstance(payload,dict):raise ValueError('Payload must be JSON object')
 with connect() as c:
  a=active(c);accepted=False;note=''
  if kind=='face':
   employee=str(payload.get('employee_id','')).strip()
   if not employee:note='employee_id required'
   else:
    # Face recognition only sets the active identity. It is NOT an inspection attempt.
    if a:c.execute('UPDATE attempts SET finished=?,reason=? WHERE id=?',(time(),'New Face Recognition; previous inspection incomplete',a['id']))
    accepted=True;note='Face identity accepted; awaiting PPE/sensor events (0 PPE attempts)'
  else:
   if not a:note='No active inspection; send Face Recognition first'
   else:
    key='temperature' if kind=='temperature' else str(payload.get('key',''))
    if key not in ALL_KEYS:note=f'Unknown inspection key: {key}'
    else:
     if key=='temperature':
      try:
       val=float(payload['value']);result='PASS' if 36<=val<=37.5 else 'FAIL'
      except (KeyError,ValueError,TypeError):result='';note='Numeric temperature value required'
     else:
      result=str(payload.get('result','')).upper()
      if result not in ('PASS','FAIL'):note='Explicit PASS or FAIL required'
     if result in ('PASS','FAIL'):
      c.execute('INSERT OR REPLACE INTO checks VALUES(?,?,?,?,?)',(a['id'],key,result,str(payload.get('source','CONFIRMED')),time()))
      status=recalculate(c,a['id']);accepted=True;note=f'{key}: {result}; overall {status}'
  c.execute('INSERT INTO events(time,event,payload,accepted,note) VALUES(?,?,?,?,?)',(time(),kind,json.dumps(payload,ensure_ascii=False),int(accepted),note))
  c.commit()
  return {'accepted':accepted,'message':note}
def snapshot():
 with connect() as c:
  a=active(c);last=c.execute('SELECT * FROM attempts ORDER BY id DESC LIMIT 1').fetchone();checks=c.execute('SELECT * FROM checks WHERE attempt_id=?',(a['id'] if a else (last['id'] if last else -1),)).fetchall();stats={r['status']:r['n'] for r in c.execute('SELECT status,count(*) n FROM attempts GROUP BY status')};return {'active':dict(a) if a else None,'latest':dict(last) if last else None,'checks':[dict(x) for x in checks],'stats':stats}
