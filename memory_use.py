"""Bounded checkpoints: durable write receipts are separate from freshness."""
import datetime as dt
import json
import os

BACKGROUND_INTERVAL_SECONDS=600


def receipt(db,marker,data):
    """An existing note is proof even after supersession or later tool work."""
    row=db.execute("SELECT id,project_id,session_id FROM entries WHERE source='note' AND source_key=?",
                   ('handoff:'+marker.stem,)).fetchone()
    if row is None and data.get('note_id'):
        row=db.execute("SELECT id,project_id,session_id FROM entries WHERE source='note' AND id=?",(data['note_id'],)).fetchone()
    if row and (not data.get('project_id') or row['project_id']==data['project_id']) and (not data.get('session_id') or row['session_id']==data['session_id']):
        return row
    return None


def finish(mem,m,platform,data,item):
    if platform!='claude':return {}
    ref=item['memory_scope'];project=mem.resolve(ref);sid=item['session'];prefix='claude:'+sid+':'
    # Every delivered prompt defines a new work batch, including task completion
    # and inter-session messages. Never lose the batch behind 20 notifications.
    prompt=mem.db.execute("SELECT id,source_key FROM entries WHERE project_id=? AND session_id=? AND kind='prompt' AND source='hook' AND substr(source_key,1,?)=? ORDER BY id DESC LIMIT 1",
                           (project['id'],sid,len(prefix),prefix)).fetchone()
    last_tool=mem.db.execute("SELECT max(id) FROM entries WHERE project_id=? AND session_id=? AND source='hook' AND title LIKE 'PostToolUse%' AND substr(source_key,1,?)=?",
                             (project['id'],sid,len(prefix),prefix)).fetchone()[0]
    note=mem.db.execute("SELECT id,created_at FROM entries WHERE project_id=? AND session_id=? AND source='note' AND state='active' AND kind IN ('handoff','decision') ORDER BY id DESC LIMIT 1",
                        (project['id'],sid)).fetchone()
    fresh=bool(note and (not last_tool or note['id']>last_tool))
    background=bool(data.get('background_tasks') or data.get('session_crons'))
    outcome={'version':2,'project_id':project['id'],'session_id':sid,'checked_at':m.now(),
             'prompt_id':prompt['id'] if prompt else None,'last_tool_id':last_tool,
             'note_id':note['id'] if note else None,'fresh':fresh,
             'background_tasks':len(data.get('background_tasks') or []),'session_crons':len(data.get('session_crons') or []),
             'stop_hook_active':bool(data.get('stop_hook_active'))}
    def done(reason,result=None):
        m.write_json_atomic(mem.home/'handoff-sessions'/(m.digest(project['id']+':'+sid)+'.json'),{**outcome,'reason':reason})
        return result or {}
    if prompt is None:return done('missing_prompt')
    marker=mem.home/'handoff-checks'/(m.digest('v2:'+project['id']+':'+sid+':'+prompt['source_key'])+'.json')
    previous=json.loads(marker.read_text(encoding='utf8')) if marker.exists() else None
    if previous:
        saved=receipt(mem.db,marker,previous)
        # Also recognize a spontaneous custom-request-id note from this batch.
        if saved is None and note and note['id']>previous.get('tool_id',note['id']):saved=note
        if saved:
            previous={**previous,'state':'saved','note_id':saved['id'],'checked_at':m.now()}
            m.write_json_atomic(marker,previous)
    if not last_tool:return done('no_tool_work')
    if not str(data.get('last_assistant_message','')).strip():return done('no_final_message')
    if fresh:return done('fresh')
    if data.get('stop_hook_active') or previous:
        if previous and previous.get('state')!='saved':
            m.write_json_atomic(marker,{**previous,'state':'not_confirmed','checked_at':m.now()})
        return done('continuation_guard' if data.get('stop_hook_active') else 'batch_already_requested')
    if background and note:
        age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(note['created_at'].replace('Z','+00:00'))).total_seconds()
        if age<BACKGROUND_INTERVAL_SECONDS:return done('recent_background_checkpoint')
    previous_handoff=mem.db.execute("SELECT id FROM entries WHERE project_id=? AND session_id=? AND source='note' AND kind='handoff' AND state='active' ORDER BY id DESC LIMIT 1",(project['id'],sid)).fetchone()
    args={**ref,'title':'Aktuální předání práce','kind':'handoff','request_id':'handoff:'+marker.stem}
    if previous_handoff:args['supersedes']=previous_handoff['id']
    marker.parent.mkdir(parents=True,exist_ok=True)
    try:
        with marker.open('x',encoding='utf8') as f:
            json.dump({'version':2,'state':'requested','requested_at':m.now(),'checked_at':m.now(),
                       'session_id':sid,'project_id':project['id'],'prompt_id':prompt['id'],'tool_id':last_tool},f)
            f.flush();os.fsync(f.fileno())
    except FileExistsError:return done('concurrent_request')
    reason=('Ulož průběžné předání této práce přes project_memory_remember jako poslední nástroj před odpovědí. '
            'Shrň ideálně do 1800 znaků aktuální cíl, platná rozhodnutí a omezení, skutečné změny a ověření se zdroji, '
            'další krok a co neopakovat. Rozpracované nebo běžící úkoly výslovně označ jako nedokončené; '
            'nečekej na ně a neruš je jen kvůli paměti. Nepřepisuj předání jiné session. '
            'Použij tyto argumenty a doplň text: '+json.dumps(args,ensure_ascii=False)+'. '
            'Při nedostupnosti nebo chybě nástroje oznam překážku; kontrola tento pracovní krok znovu blokovat nebude.')
    return done('requested',{'decision':'block','reason':reason})


def status(home,db=None):
    counts={}
    for p in (home/'handoff-checks').glob('*.json'):
        try:
            data=json.loads(p.read_text(encoding='utf8'))
            state='saved' if db is not None and receipt(db,p,data) else data['state']
        except (OSError,ValueError,KeyError):state='unreadable'
        counts[state]=counts.get(state,0)+1
    return counts


def sessions(home):
    rows=[]
    for p in (home/'handoff-sessions').glob('*.json'):
        try:rows.append(json.loads(p.read_text(encoding='utf8')))
        except (OSError,ValueError):rows.append({'reason':'unreadable','file':p.name})
    return sorted(rows,key=lambda r:r.get('checked_at',''),reverse=True)[:20]


def repair_receipts(mem,m):
    """Reconcile old status files from durable evidence, never rewrite notes."""
    changed=0
    for p in (mem.home/'handoff-checks').glob('*.json'):
        data=json.loads(p.read_text(encoding='utf8'));row=receipt(mem.db,p,data)
        if row and (data.get('state')!='saved' or data.get('note_id')!=row['id']):
            m.write_json_atomic(p,{**data,'state':'saved','note_id':row['id'],'project_id':row['project_id'],
                                  'session_id':row['session_id'],'checked_at':m.now()});changed+=1
    return changed
