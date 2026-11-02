"""Incremental recovery of completed tool events from local host transcripts.

Transcripts are data, never commands. Separate provenance prevents a recovered
representation from conflicting with a later native hook. No network access.
"""
import contextlib
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.parse


def prepare(mem):
    # Cover the de-duplication lookup without visiting large event bodies.
    mem.db.execute('CREATE INDEX IF NOT EXISTS entries_capture_lookup ON entries(session_id,source,source_key)')
    mem.db.execute('CREATE INDEX IF NOT EXISTS entries_claude_tool_lookup ON entries(project_id,substr(source_key,-30),source)')
    mem.db.execute('''CREATE TABLE IF NOT EXISTS transcript_cursors(
        path TEXT PRIMARY KEY,platform TEXT NOT NULL,session_id TEXT NOT NULL,
        offset INTEGER NOT NULL DEFAULT 0,mtime_ns INTEGER NOT NULL DEFAULT 0,
        cwd TEXT,last_scan TEXT NOT NULL,recovered INTEGER NOT NULL DEFAULT 0)''')
    mem.db.execute('''CREATE TABLE IF NOT EXISTS transcript_calls(
        path TEXT NOT NULL,call_id TEXT NOT NULL,payload TEXT NOT NULL,
        PRIMARY KEY(path,call_id))''')
    if 'memory_sid' not in {r[1] for r in mem.db.execute('PRAGMA table_info(transcript_cursors)')}:
        mem.db.execute('ALTER TABLE transcript_cursors ADD COLUMN memory_sid TEXT')


def diagnostic(mem,m,tool,error):
    message=m.safe_text(str(error))[:700]
    if not mem.db.execute('SELECT 1 FROM memory_diagnostics WHERE stage=? AND tool=? AND message=? AND resolved_at IS NULL',
                          ('reconcile',tool,message)).fetchone():
        mem.db.execute('INSERT INTO memory_diagnostics(created_at,stage,tool,message) VALUES(?,?,?,?)',
                       (m.now(),'reconcile',tool,message))


def native_exists(mem,sid,tool_id):
    # Native subagent keys may include a host-specific agent ID.
    suffix=':'+tool_id
    return mem.db.execute("SELECT id FROM entries WHERE source='hook' AND session_id=? AND substr(source_key,-?)=? LIMIT 1",
                          (sid,len(suffix),suffix)).fetchone() is not None


def existing_claude_tool(mem,project_id,tool_id,note=False):
    # Claude forks may rewrite sessionId on copied events. Their random toolu_
    # identifiers remain stable. Deduplicate only within the verified project;
    # never borrow the foreign session's identity or content.
    if not re.fullmatch(r'toolu_[A-Za-z0-9]{24}',tool_id):return False
    condition="source='note' AND source_key LIKE 'transcript-note:claude:%'" if note else "source IN ('hook','transcript') AND source_key LIKE 'claude:%'"
    return mem.db.execute('SELECT 1 FROM entries WHERE project_id=? AND substr(source_key,-30)=? AND '+condition+' LIMIT 1',
                          (project_id,tool_id)).fetchone() is not None


def supersede_fork_copies(mem):
    # Retain reconstructed bytes, but one host event has only one active copy.
    return mem.db.execute("""UPDATE entries AS r SET state='superseded'
        WHERE r.source='transcript' AND r.source_key LIKE 'claude:%' AND r.state='active'
        AND substr(r.source_key,-30,6)='toolu_' AND EXISTS(
            SELECT 1 FROM entries n WHERE n.project_id=r.project_id
            AND substr(n.source_key,-30)=substr(r.source_key,-30)
            AND n.source_key LIKE 'claude:%' AND (n.source='hook' OR (n.source='transcript' AND n.id<r.id)))""").rowcount


def preserve_failure(mem,m,path,call,result,error):
    key=m.digest(str(path)+':'+call['id'])
    payload={'path':str(path),'call':call,'result':result,'is_error':error}
    if m.secret_file_event({'tool_input':call['input']}):payload['result']='Credential file result intentionally omitted.'
    m.write_json_atomic(mem.home/'transcript-retry'/(key+'.json'),m.redact(payload))


def recover_note(mem,m,platform,sid,cwd,tool_id,args,created):
    args=m.normalize_tool_args(args)
    # Missing wrappers are recoverable only from the transcript's independently
    # identified session and directory. Conflicting explicit identity is refused.
    ref=m.scope_args(cwd,sid,platform)
    expected=mem.resolve(ref)
    supplied={k:args.get(k,ref[k]) for k in ref}
    if mem.resolve(supplied)['id']!=expected['id']:
        raise ValueError('Failed note belongs to a different scope; automatic recovery refused.')
    if platform=='claude' and existing_claude_tool(mem,expected['id'],tool_id,note=True):return 0
    title=args.get('title');text=args.get('text');kind=args.get('kind','fact')
    if not isinstance(title,str) or not isinstance(text,str) or kind not in m.KINDS:
        raise ValueError('Failed note has no recoverable title/text/kind.')
    key='transcript-note:'+platform+':'+sid+':'+tool_id
    if mem.db.execute("SELECT 1 FROM entries WHERE source='note' AND source_key=?",(key,)).fetchone():return 0
    existing=mem.db.execute("SELECT * FROM entries WHERE project_id=? AND source='note' AND title=? AND state='active' ORDER BY created_at DESC LIMIT 1",
                            (expected['id'],title)).fetchone()
    body='[Recovered historical note; original attempt '+created+'. Verify against newer decisions.]\n'+text
    row=mem.insert(expected['id'],kind,title,body,'note',key,created=created,session=sid,cwd=cwd)
    if existing:
        if existing['source_key'].startswith('transcript-note:') and existing['session_id']==sid and existing['created_at']<=created:
            mem.db.execute("UPDATE entries SET state='superseded' WHERE id=?",(existing['id'],))
            mem.db.execute('UPDATE entries SET supersedes=? WHERE id=?',(existing['id'],row['id']))
        else:
            # A current agent-authored note wins over a reconstructed attempt.
            mem.db.execute("UPDATE entries SET state='superseded' WHERE id=?",(row['id'],))
    mem.db.execute('INSERT INTO memory_diagnostics(created_at,stage,tool,message,resolved_at,resolution) VALUES(?,?,?,?,?,?)',
                   (m.now(),'reconcile','project_memory_remember','Recovered failed historical note '+tool_id,m.now(),'entry '+str(row['id'])))
    return 1


def recover_tool(mem,m,call,result,is_error=False):
    platform=call['platform'];sid=call['sid'];tool_id=call['id'];name=call['name']
    if 'project_memory' in name or 'project-memory' in name:
        if 'project_memory_remember' in name and is_error:
            return recover_note(mem,m,platform,sid,call['cwd'],tool_id,call['input'],call['timestamp'])
        return 0
    event='PostToolUseFailure' if is_error else 'PostToolUse'
    key=platform+':'+sid+'::'+event+':'+tool_id
    if native_exists(mem,sid,tool_id) or mem.db.execute("SELECT 1 FROM entries WHERE source='transcript' AND source_key=?",(key,)).fetchone():return 0
    data={'cwd':call['cwd'],'session_id':sid,'tool_use_id':tool_id,'tool_name':name,
          'tool_input':call['input'],'tool_response':result}
    try:
        item=m.prepare_event(platform,event,data)
        if item is None:return 0
        project=mem.resolve(item['memory_scope'])
    except ValueError:
        # A historical scratch directory may have been removed after the tool
        # finished. Reuse only a unique *recorded* identity for this exact
        # host/session/path. Never infer an archive from a folder name.
        chosen=call['input'].get('workdir') if isinstance(call['input'],dict) else None
        chosen=chosen or call['cwd']
        if not chosen or not Path(chosen).is_absolute() or Path(chosen).exists():raise
        chosen=os.path.normcase(str(Path(chosen).resolve()))
        prefix=platform+':'+sid+':'
        known=mem.db.execute("SELECT DISTINCT project_id FROM entries WHERE source='hook' AND session_id=? AND cwd=? AND substr(source_key,1,?)=?",
                             (sid,chosen,len(prefix),prefix)).fetchall()
        if len(known)!=1:raise ValueError('Removed directory has no unique recorded host/session identity.')
        project={'id':known[0]['project_id']}
        payload={k:data[k] for k in ('tool_name','tool_input','tool_response')}
        if m.secret_file_event(data):payload={'tool_name':name,'omitted':'Potential credential file; content intentionally not captured.'}
        item={'title':event+' '+name,'body':m.safe_text(payload),'cwd':chosen}
    if platform=='claude' and existing_claude_tool(mem,project['id'],tool_id):return 0
    mem.insert(project['id'],'event',item['title'],item['body'],'transcript',key,
               created=call['timestamp'],session=sid,cwd=item['cwd'])
    return 1


def path_from_uri(value):
    if isinstance(value,str) and value.startswith('file:'):
        value=urllib.parse.unquote(urllib.parse.urlsplit(value).path)
        if re.match(r'^/[A-Za-z]:',value):value=value[1:]
    return value


def scan(mem,m,path,platform,sid,since,seconds=2,max_bytes=16_000_000):
    prepare(mem);path=Path(path).resolve();key=str(path)
    prior=mem.db.execute('SELECT * FROM transcript_cursors WHERE path=?',(key,)).fetchone()
    stat=path.stat();offset=prior['offset'] if prior and prior['offset']<=stat.st_size else 0
    if prior and offset==stat.st_size and prior['mtime_ns']==stat.st_mtime_ns:return {'recovered':0,'complete':True,'offset':offset}
    cwd=prior['cwd'] if prior else None;memory_sid=(prior['memory_sid'] if prior else None) or sid
    began=time.monotonic();start_offset=offset;recovered=0
    with path.open('rb') as stream:
        stream.seek(offset)
        while time.monotonic()-began<seconds and stream.tell()-start_offset<max_bytes:
            begin=stream.tell();raw=stream.readline()
            if not raw:break
            if not raw.endswith(b'\n'):stream.seek(begin);break
            if raw.startswith((b'{"type":"api-request-blob"',b'{"type":"api-request"')):continue
            try:o=json.loads(raw)
            except (ValueError,UnicodeError) as e:
                diagnostic(mem,m,key,'Invalid complete transcript line at byte '+str(begin)+': '+str(e));continue
            timestamp=o.get('timestamp','')
            if platform=='codex':
                payload=o.get('payload',{})
                if o.get('type') in ('session_meta','turn_context'):
                    if o.get('type')=='session_meta':
                        if begin==0 and payload.get('id') not in (None,sid):
                            raise ValueError('Transcript identity differs from filename.')
                        # A child rollout contains inherited parent metadata and
                        # events. Native hooks store child tools under the root
                        # session. Follow explicit ancestry, never infer by cwd.
                        if payload.get('id') in (sid,memory_sid):
                            source=payload.get('source',{})
                            parent=source.get('subagent',{}).get('thread_spawn',{}).get('parent_thread_id') if isinstance(source,dict) else None
                            if parent:memory_sid=parent
                    cwd=path_from_uri(payload.get('cwd',cwd));continue
                if timestamp<since or o.get('type')!='event_msg' or payload.get('type')!='item_completed':continue
                # Parent transcripts can contain completion notices for subagents.
                actual_sid=payload.get('thread_id',sid)
                if actual_sid!=sid:continue
                item=payload.get('item',{});typ=item.get('type');tool_id=item.get('id')
                if not tool_id:continue
                if typ=='CommandExecution':name='Bash';inp={'command':item.get('command'),'workdir':path_from_uri(item.get('cwd'))};result=item.get('aggregated_output');error=item.get('exit_code',0) not in (0,None)
                elif typ=='McpToolCall':name='mcp__'+str(item.get('server'))+'__'+str(item.get('tool'));inp=item.get('arguments',{});result=item.get('result');error=item.get('status')=='failed' or (isinstance(result,dict) and result.get('isError',False))
                elif typ=='FileChange':name='apply_patch';inp={'changes':item.get('changes')};result={'stdout':item.get('stdout'),'stderr':item.get('stderr')};error=item.get('status')=='failed'
                elif typ=='ImageView':name='view_image';inp={'path':item.get('path')};result={'viewed_path':item.get('path')};error=False
                elif typ=='Extension':name=str(item.get('kind','Extension'));inp={'prompt':item.get('revisedPrompt'),'inputImages':item.get('inputImages')};result=item;error=bool(item.get('failure'))
                else:continue
                if isinstance(inp,str):
                    try:inp=json.loads(inp)
                    except ValueError:inp={'raw':inp}
                call={'platform':platform,'sid':memory_sid,'cwd':cwd,'id':tool_id,'name':name,'input':inp,'timestamp':timestamp}
                try:
                    with mem.transaction():recovered+=recover_tool(mem,m,call,result,error)
                except Exception as e:
                    preserve_failure(mem,m,key,call,result,error)
                    diagnostic(mem,m,key,str(tool_id)+': '+str(e))
                continue
            if o.get('sessionId')!=sid:continue
            cwd=o.get('cwd') or cwd
            if timestamp<since:continue
            content=o.get('message',{}).get('content',[])
            if not isinstance(content,list):continue
            if o.get('type')=='assistant':
                for block in content:
                    if not isinstance(block,dict) or block.get('type')!='tool_use':continue
                    call={'platform':platform,'sid':sid,'cwd':cwd,'id':block['id'],'name':block.get('name',''),'input':block.get('input',{}),'timestamp':timestamp}
                    if native_exists(mem,sid,call['id']):continue
                    mem.db.execute('INSERT OR REPLACE INTO transcript_calls VALUES(?,?,?)',(key,call['id'],m.safe_text(call)))
            elif o.get('type')=='user':
                for block in content:
                    if not isinstance(block,dict) or block.get('type')!='tool_result':continue
                    tool_id=block.get('tool_use_id')
                    saved=mem.db.execute('SELECT payload FROM transcript_calls WHERE path=? AND call_id=?',(key,tool_id)).fetchone()
                    if not saved:continue
                    call=json.loads(saved['payload'])
                    try:
                        with mem.transaction():
                            recovered+=recover_tool(mem,m,call,block.get('content'),bool(block.get('is_error')))
                            mem.db.execute('DELETE FROM transcript_calls WHERE path=? AND call_id=?',(key,tool_id))
                    except Exception as e:
                        preserve_failure(mem,m,key,call,block.get('content'),bool(block.get('is_error')))
                        diagnostic(mem,m,key,str(tool_id)+': '+str(e))
        offset=stream.tell()
    # Native inserts arriving later supersede reconstructed representations,
    # retaining provenance without two active copies of the same tool event.
    mem.db.execute('''UPDATE entries AS recovered SET state='superseded'
        WHERE source='transcript' AND session_id=? AND state='active' AND EXISTS(
        SELECT 1 FROM entries native WHERE native.source='hook' AND native.session_id=recovered.session_id
        AND substr(native.source_key,-length(substr(recovered.source_key,instr(recovered.source_key,'::')+2)))=
            substr(recovered.source_key,instr(recovered.source_key,'::')+2))''',(memory_sid,))
    mem.db.execute('''INSERT INTO transcript_cursors(path,platform,session_id,offset,mtime_ns,cwd,last_scan,recovered,memory_sid)
        VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(path) DO UPDATE SET
        offset=excluded.offset,mtime_ns=excluded.mtime_ns,cwd=excluded.cwd,last_scan=excluded.last_scan,
        recovered=transcript_cursors.recovered+excluded.recovered,memory_sid=excluded.memory_sid''',
        (key,platform,sid,offset,stat.st_mtime_ns,cwd,m.now(),recovered,memory_sid))
    if platform=='claude':supersede_fork_copies(mem)
    return {'recovered':recovered,'complete':offset>=stat.st_size,'offset':offset}


@contextlib.contextmanager
def worker_lock(home):
    lock=Path(home)/'reconcile.lock';lock.parent.mkdir(parents=True,exist_ok=True)
    with lock.open('a+b') as f:
        if f.seek(0,2)==0:f.write(b'0');f.flush()
        f.seek(0)
        if os.name=='nt':
            import msvcrt
            try:msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:yield False;return
            try:yield True
            finally:f.seek(0);msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
        else:
            import fcntl
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError:yield False;return
            try:yield True
            finally:fcntl.flock(f,fcntl.LOCK_UN)


def run(mem,m,config,seconds=8):
    prepare(mem);start=time.monotonic();total=0;files=0
    since=config['since'];epoch=dt.datetime.fromisoformat(since.replace('Z','+00:00')).timestamp()
    with worker_lock(mem.home) as acquired:
        if not acquired:return {'busy':True,'recovered':0}
        for retry in (mem.home/'transcript-retry').glob('*.json'):
            if time.monotonic()-start>=seconds:break
            try:
                item=json.loads(retry.read_text(encoding='utf8'))
                with mem.transaction():total+=recover_tool(mem,m,item['call'],item['result'],item['is_error'])
                retry.unlink(missing_ok=True)
                mem.db.execute("UPDATE memory_diagnostics SET resolved_at=?,resolution=? WHERE stage='reconcile' AND tool=? AND message LIKE ? AND resolved_at IS NULL",
                               (m.now(),'transcript retry completed',item['path'],item['call']['id']+':%'))
            except Exception as e:diagnostic(mem,m,str(retry),e)
        candidates=[]
        for platform,root in config['roots'].items():
            root=Path(root)
            paths=root.glob('*/*.jsonl') if platform=='claude' else root.rglob('*.jsonl')
            for path in paths:
                stat=path.stat()
                if stat.st_mtime<epoch:continue
                sid=path.stem if platform=='claude' else path.stem[-36:]
                if not re.fullmatch(r'[0-9a-fA-F-]{36}',sid):continue
                prior=mem.db.execute('SELECT offset,mtime_ns,last_scan FROM transcript_cursors WHERE path=?',(str(path.resolve()),)).fetchone()
                if prior and prior['offset']==stat.st_size and prior['mtime_ns']==stat.st_mtime_ns:continue
                candidates.append((prior['last_scan'] if prior else '',platform,str(path),sid))
        for _,platform,path,sid in sorted(candidates):
            if time.monotonic()-start>=seconds:break
            try:
                result=scan(mem,m,path,platform,sid,since,seconds=min(2,max(.1,seconds-(time.monotonic()-start))))
                total+=result['recovered'];files+=1
            except Exception as e:diagnostic(mem,m,path,e)
        m.write_json_atomic(mem.home/'reconcile-status.json',{'checked_at':m.now(),'files_processed':files,'files_waiting_at_start':len(candidates),'recovered_this_run':total})
    return {'recovered':total,'files':files,'candidates':len(candidates)}


def kick(home):
    """Short on-demand repair process, not a scheduler or permanent daemon."""
    home=Path(home);config=home/'reconcile-config.json'
    if not config.exists():return
    value=json.loads(config.read_text(encoding='utf8'))
    if not value.get('enabled'):return
    # The worker lock handles concurrent hosts; no host/app restart is needed.
    with (home/'reconcile-worker.log').open('ab') as log:
        subprocess.Popen([sys.executable,str(Path(__file__).with_name('memory.py')),'--home',str(home),'reconcile'],
                         stdin=subprocess.DEVNULL,stdout=log,stderr=log,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),close_fds=True)
