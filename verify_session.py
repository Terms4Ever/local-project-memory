"""Exercise installed hook commands and MCP processes, without creating chats."""
import contextlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import uuid
from memory import Memory, VERSION, scope_args, write_json_atomic
from verify_codex import owned

def verify(hosts=('claude','codex')):
    home=Path.home()/'.project-memory'
    script=home/'app/memory.py'
    uid='session-verification-'+uuid.uuid4().hex
    marker='memoryprobe'+uuid.uuid4().hex
    configs={host:json.loads((Path.home()/folder/file).read_text(encoding='utf8'))
             for host,folder,file in [('claude','.claude','settings.json'),('codex','.codex','hooks.json')] if host in hosts}
    checks=[]
    for host,cfg in configs.items():
        def run_hook(event,data):
            commands=[h['command'] for group in cfg['hooks'][event] for h in group['hooks']
                      if owned(h.get('command',''),str(script))]
            assert len(commands)==1,(host,event,len(commands))
            p=subprocess.run(commands[0],shell=True,input=json.dumps(data),text=True,
                             capture_output=True,encoding='utf8',timeout=30,
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            assert p.returncode==0,p.stderr
            return json.loads(p.stdout)
        data={'session_id':uid}
        first=run_hook('SessionStart',data)
        assert 'LOCAL SESSION MEMORY' in first['hookSpecificOutput']['additionalContext']
        run_hook('UserPromptSubmit',{**data,'prompt':marker+' '+host})
        run_hook('Stop',{**data,'last_assistant_message':'Diagnostic session verification only.'})
        resumed=run_hook('SessionStart',data)
        assert marker in resumed['hookSpecificOutput']['additionalContext']
        foreign=run_hook('SessionStart',{'session_id':uid+'-other'})
        assert marker not in foreign['hookSpecificOutput']['additionalContext']
        checks.append({'host':host,'installed_hooks':'passed','no_cwd':'passed',
                       'resume_in_new_process':'passed','other_session_isolation':'passed'})
    def call_mcp(name,args):
        req={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':name,'arguments':args}}
        p=subprocess.run([sys.executable,str(script),'serve'],input=json.dumps(req)+'\n',
                         text=True,capture_output=True,encoding='utf8',timeout=30,
                         creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert p.returncode==0,p.stderr
        result=json.loads(p.stdout)['result']
        assert not result.get('isError'),result
        return json.loads(result['content'][0]['text'])
    ref={'platform':hosts[0],'session_id':uid,'scope':'session'}
    entry=call_mcp('project_memory_remember',{**ref,'title':'Diagnostic session probe',
        'text':marker+' durable diagnostic note','kind':'fact','request_id':uid})
    restored=call_mcp('project_memory_read',{**ref,'ids':[entry['id']]})
    assert marker in restored['entries'][0]['body']
    other=call_mcp('project_memory_search',{**ref,'session_id':uid+'-other','query':marker})
    assert other['entries']==[]
    state=call_mcp('project_memory_status',ref)
    assert state['version']==VERSION and state['scope']=='session'
    with contextlib.closing(Memory(home)) as mem:
        with tempfile.TemporaryDirectory(prefix='memory-git-check-') as project:
            subprocess.run(['git','init',project],check=True,capture_output=True,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            assert mem.resolve(scope_args(project,uid,hosts[0]))['identity'].startswith('git:')
        integrity=mem.db.execute('PRAGMA integrity_check').fetchone()[0]
        violations=mem.db.execute('PRAGMA foreign_key_check').fetchall()
        assert integrity=='ok' and not violations
        status=mem.status()
    result={'version':VERSION,'checks':checks,'mcp_persistence_and_isolation':'passed',
            'git_still_project':'passed','integrity':integrity,'foreign_key_violations':len(violations),
            'pending_events':status['pending_events'],'failed_replays':status['failed_replays'],
            'diagnostic_session_id':uid,'ordinary_desktop_chat_tested':False}
    write_json_atomic(home/'session-verification.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',choices=['claude','codex','both'],default='both')
    args=parser.parse_args()
    verify(('claude','codex') if args.host=='both' else (args.host,))
