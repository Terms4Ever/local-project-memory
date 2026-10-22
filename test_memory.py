import concurrent.futures
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from memory import Memory, canonical, digest, dispatch, hook, prepare_event, record_event, redact, replay, scope_args, write_json_atomic
from import_legacy import migrate
from install import setup, rollback

def concurrent_write(args):
    home,cwd,index=args
    with contextlib.closing(Memory(home)) as m:
        return m.remember(cwd,'Concurrent '+str(index),'Preserve item '+str(index),request_id='concurrent-'+str(index))['id']

def concurrent_session_write(args):
    home,cwd,index=args
    with contextlib.closing(Memory(home)) as m:
        ref=scope_args(cwd,'parallel-'+str(index%4),'codex')
        return m.remember(ref,'Session item','marker'+str(index%4),request_id='session-parallel-'+str(index))['id']

class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name)
        self.home=self.base/'state';self.a=self.base/'a';self.b=self.base/'b'
        self.a.mkdir();self.b.mkdir();self.mem=Memory(self.home)
    def tearDown(self):
        self.mem.close();self.tmp.cleanup()
    def git(self,*args):
        subprocess.run(['git',*map(str,args)],check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    def test_project_isolation_and_read_denial(self):
        a=self.mem.remember(str(self.a),'A','dragon ONLY_A',request_id='a')
        b=self.mem.remember(str(self.b),'B','dragon ONLY_B',request_id='b')
        result=self.mem.search(str(self.a),'dragon')
        self.assertEqual([r['id'] for r in result['entries']],[a['id']])
        self.assertNotIn('ONLY_B',self.mem.context(str(self.a)))
        with self.assertRaises(ValueError):self.mem.read(str(self.a),[b['id']])

    def test_exact_non_git_and_registered_children(self):
        sub=self.a/'sub';sub.mkdir()
        self.assertNotEqual(self.mem.resolve(str(self.a))['id'],self.mem.resolve(str(sub))['id'])
        self.mem.register(str(self.a))
        self.assertEqual(self.mem.resolve(str(self.a))['id'],self.mem.resolve(str(sub))['id'])
        sibling=self.base/'a-other';sibling.mkdir()
        self.assertNotEqual(self.mem.resolve(str(self.a))['id'],self.mem.resolve(str(sibling))['id'])

    def test_nested_repo_overrides_parent_alias(self):
        self.mem.register(str(self.a));sub=self.a/'nested';sub.mkdir();self.git('init',sub)
        self.assertNotEqual(self.mem.resolve(str(self.a))['id'],self.mem.resolve(str(sub))['id'])

    def test_worktree_shares_identity_independent_clone_does_not(self):
        self.git('init',self.a)
        self.git('-C',self.a,'-c','user.name=Test','-c','user.email=test@example.invalid','commit','--allow-empty','-m','fixture')
        wt=self.base/'worktree';self.git('-C',self.a,'worktree','add','--detach',wt)
        self.git('clone',self.a,self.b)
        self.assertEqual(self.mem.resolve(str(self.a))['id'],self.mem.resolve(str(wt))['id'])
        self.assertNotEqual(self.mem.resolve(str(self.a))['id'],self.mem.resolve(str(self.b))['id'])

    @unittest.skipUnless(os.name=='nt','Windows case semantics')
    def test_windows_case_and_slashes(self):
        self.assertEqual(self.mem.resolve(str(self.a))['id'],self.mem.resolve(str(self.a).upper().replace('\\','/'))['id'])

    def test_missing_cwd_refused(self):
        with self.assertRaises(ValueError):self.mem.resolve('.')
        with self.assertRaises(ValueError):self.mem.resolve(str(self.base/'missing'))
        with self.assertRaises(ValueError):prepare_event('claude','Stop',{})
        with self.assertRaises(ValueError):prepare_event('claude','Stop',{'cwd':str(self.base/'missing'),'session_id':'x'})

    def test_broken_git_identity_refuses_fallback(self):
        (self.a/'.git').mkdir()
        with self.assertRaises(ValueError):self.mem.resolve(str(self.a))

    def test_idempotency_and_collision(self):
        a=self.mem.remember(str(self.a),'A','same',request_id='retry')
        b=self.mem.remember(str(self.a),'A','same',request_id='retry')
        self.assertEqual(a['id'],b['id'])
        with self.assertRaises(ValueError):self.mem.remember(str(self.b),'A','same',request_id='retry')
        with self.assertRaises(ValueError):self.mem.remember(str(self.a),'A','changed',request_id='retry')

    def test_atomic_supersession_and_stale_writer(self):
        a=self.mem.remember(str(self.a),'Rule','old',kind='decision',request_id='old')
        b=self.mem.remember(str(self.a),'Rule','new',kind='decision',request_id='new',supersedes=a['id'])
        with self.assertRaises(ValueError):self.mem.remember(str(self.a),'Rule','conflict',request_id='stale',supersedes=a['id'])
        self.assertEqual(self.mem.read(str(self.a),[a['id']])['entries'][0]['state'],'superseded')
        self.assertEqual([x['id'] for x in self.mem.search(str(self.a),'Rule')['entries']],[b['id']])
        self.assertEqual(self.mem.remember(str(self.a),'Rule','new',kind='decision',request_id='new',supersedes=a['id'])['id'],b['id'])

    def test_cross_project_supersede_refused(self):
        a=self.mem.remember(str(self.a),'A','old')
        with self.assertRaises(ValueError):self.mem.remember(str(self.b),'B','new',supersedes=a['id'])

    def test_restart_persistence_and_backup(self):
        a=self.mem.remember(str(self.a),'Persistent','keep me')
        backup=self.mem.backup()
        with contextlib.closing(Memory(self.home)) as m:self.assertEqual(m.read(str(self.a),[a['id']])['entries'][0]['body'],'keep me')
        with contextlib.closing(sqlite3.connect(backup)) as c:self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_concurrent_processes_no_loss(self):
        jobs=[(str(self.home),str(self.a),i) for i in range(36)]
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:ids=list(pool.map(concurrent_write,jobs))
        self.assertEqual(len(set(ids)),36)
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],36)

    def test_killed_writer_leaves_no_partial_transaction(self):
        code="""import sys
from memory import Memory
m=Memory(sys.argv[1]);p=m.resolve(sys.argv[2])
m.db.execute('BEGIN IMMEDIATE')
m.insert(p['id'],'fact','uncommitted','must roll back','test','crash')
print('ready',flush=True)
sys.stdin.readline()
"""
        proc=subprocess.Popen([sys.executable,'-c',code,str(self.home),str(self.a)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            self.assertEqual(proc.stdout.readline().strip(),'ready')
            proc.kill();proc.wait(timeout=10)
        finally:
            if proc.poll() is None:proc.kill();proc.wait()
            proc.stdin.close();proc.stdout.close();proc.stderr.close()
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],0)
        self.assertEqual(self.mem.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

    def test_sqlite_lock_spool_and_replay(self):
        event=prepare_event('claude','UserPromptSubmit',{'cwd':str(self.a),'session_id':'session','prompt':'locked write'})
        file=self.home/'pending'/'fixture.json';write_json_atomic(file,event)
        with contextlib.closing(Memory(self.home,timeout=.05)) as other:
            self.mem.db.execute('BEGIN IMMEDIATE')
            try:
                with self.assertRaises(sqlite3.OperationalError):record_event(other,event)
                self.assertTrue(file.exists())
            finally:self.mem.db.execute('ROLLBACK')
        self.assertEqual(replay(self.mem),1)
        self.assertFalse(file.exists());self.assertEqual(len(self.mem.search(event['memory_scope'],'locked')['entries']),1)

    def test_interrupted_journal_replay_is_idempotent(self):
        event=prepare_event('claude','PostToolUse',{'cwd':str(self.a),'session_id':'session','tool_use_id':'id1','tool_name':'Read','tool_response':'saved'})
        record_event(self.mem,event)
        write_json_atomic(self.home/'pending'/'fixture.json',event)
        self.assertEqual(replay(self.mem),1)
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],1)

    def test_bad_replay_is_preserved_and_reported(self):
        write_json_atomic(self.home/'pending'/'bad.json',{'bad':True})
        replay(self.mem)
        self.assertEqual(self.mem.status()['failed_replays'],1)
        self.assertIsNotNone(self.mem.status()['last_error_file'])

    def test_hook_context_and_no_self_capture(self):
        result=hook('claude','SessionStart',{'cwd':str(self.a),'session_id':'session'},self.home)
        self.assertEqual(result['hookSpecificOutput']['hookEventName'],'SessionStart')
        self.assertIn(self.mem.resolve(scope_args(str(self.a),'session','claude'))['id'],result['hookSpecificOutput']['additionalContext'])
        self.assertEqual(hook('codex','PostToolUse',{'cwd':str(self.a),'session_id':'session','tool_name':'mcp__project_memory__project_memory_search'},self.home),{})

    def test_explicit_tool_workdir_selects_actual_project(self):
        event=prepare_event('codex','PostToolUse',{'cwd':str(self.a),'session_id':'session','tool_name':'exec_command','tool_input':{'workdir':str(self.b),'cmd':'read file'},'tool_response':'B_ONLY'})
        record_event(self.mem,event)
        self.assertEqual(self.mem.search(str(self.a),'B_ONLY')['entries'],[])
        self.assertEqual(len(self.mem.search(str(self.b),'B_ONLY')['entries']),1)

    def test_redaction_and_sensitive_file_omission(self):
        text=redact('password=abc Bearer abc123 sk-abcdefghijklmnop')
        self.assertNotIn('abc',text)
        item=prepare_event('claude','PostToolUse',{'cwd':str(self.a),'session_id':'x','tool_input':{'file_path':str(self.a/'.env')},'tool_response':'UNKNOWN_SECRET'})
        self.assertNotIn('UNKNOWN_SECRET',item['body'])
        self.assertEqual(redact({'api_key':'x'})['api_key'],'[REDACTED]')

    def test_repeated_prompt_not_lost_without_host_event_id(self):
        data={'cwd':str(self.a),'session_id':'s','prompt':'Please correct it'}
        for _ in range(2):record_event(self.mem,prepare_event('claude','UserPromptSubmit',data))
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],2)

    def test_multiple_tools_in_same_turn_without_tool_id(self):
        for response in ('first','second'):
            data={'cwd':str(self.a),'session_id':'s','turn_id':'turn','tool_name':'Read','tool_response':response}
            record_event(self.mem,prepare_event('codex','PostToolUse',data))
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],2)

    def test_fts_special_characters_and_czech(self):
        self.mem.remember(str(self.a),'Rytíř','Útok draka a brnění')
        self.assertEqual(len(self.mem.search(str(self.a),'"utok" OR (brneni)*')['entries']),1)
        self.assertEqual(self.mem.search(str(self.b),'utok')['entries'],[])

    def test_large_note_refused(self):
        with self.assertRaises(ValueError):self.mem.remember(str(self.a),'huge','x'*24001)

    def test_folderless_sessions_and_hosts_are_isolated(self):
        a=scope_args(None,'same','claude','session')
        b=scope_args(None,'other','claude','session')
        c=scope_args(None,'same','codex','session')
        entry=self.mem.remember(a,'Private session','amber otter',request_id='session-note')
        self.assertEqual(len(self.mem.search(a,'amber')['entries']),1)
        for other in (b,c):
            self.assertEqual(self.mem.search(other,'amber')['entries'],[])
            with self.assertRaises(ValueError):self.mem.read(other,[entry['id']])
            with self.assertRaises(ValueError):self.mem.remember(other,'Other','replacement',supersedes=entry['id'])
        self.assertIsNone(entry['cwd'])
        self.assertEqual(entry['session_id'],'same')

    def test_same_default_cwd_does_not_share_sessions(self):
        for sid,prompt in [('one','amber'),('two','violet')]:
            hook('codex','UserPromptSubmit',{'cwd':str(self.a),'session_id':sid,'prompt':prompt},self.home)
        one=scope_args(str(self.a),'one','codex')
        two=scope_args(str(self.a),'two','codex')
        self.assertEqual(self.mem.search(one,'violet')['entries'],[])
        self.assertEqual(self.mem.search(two,'amber')['entries'],[])
        self.assertEqual(self.mem.search(str(self.a),'amber')['entries'],[])
        self.assertIn('MEMORY_SCOPE:',self.mem.context(one,brief=True))
        self.assertIn('LOCAL SESSION MEMORY',self.mem.context(one))

    def test_session_survives_restart_and_technical_cwd_change(self):
        ref=scope_args(str(self.a),'resume-id','codex')
        entry=self.mem.remember(ref,'Resume','persistent maple')
        with contextlib.closing(Memory(self.home)) as other:
            moved=scope_args(str(self.b),'resume-id','codex')
            self.assertEqual(other.read(moved,[entry['id']])['entries'][0]['body'],'persistent maple')
            self.assertEqual(other.status(moved)['scope'],'session')

    def test_concurrent_sessions_same_cwd_no_cross_capture(self):
        jobs=[(str(self.home),str(self.a),i) for i in range(36)]
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            ids=list(pool.map(concurrent_session_write,jobs))
        self.assertEqual(len(set(ids)),36)
        for i in range(4):
            ref=scope_args(str(self.a),'parallel-'+str(i),'codex')
            self.assertEqual(len(self.mem.search(ref,'marker'+str(i),30)['entries']),9)
            self.assertEqual(self.mem.search(ref,'marker'+str((i+1)%4))['entries'],[])

    def test_folder_attachment_does_not_merge_previous_session(self):
        ref=scope_args(str(self.a),'s','claude')
        entry=self.mem.remember(ref,'Before','session exclusive')
        self.mem.register(str(self.a))
        self.assertEqual(self.mem.status(ref)['scope'],'project')
        self.assertEqual(self.mem.search(ref,'exclusive')['entries'],[])
        explicit=scope_args(str(self.a),'s','claude','session')
        self.assertEqual(self.mem.read(explicit,[entry['id']])['entries'][0]['body'],'session exclusive')
        # Removing technical cwd also accesses the preserved session.
        self.assertEqual(self.mem.resolve(explicit)['id'],self.mem.resolve(scope_args(None,'s','claude'))['id'])

    def test_registered_folder_and_git_still_share_across_sessions(self):
        self.mem.register(str(self.a));self.git('init',self.b)
        for path in (self.a,self.b):
            one=scope_args(str(path),'one','claude');two=scope_args(str(path),'two','codex')
            self.assertEqual(self.mem.resolve(one)['id'],self.mem.resolve(two)['id'])
            self.assertEqual(self.mem.resolve(one)['id'],self.mem.resolve(str(path))['id'])

    def test_same_workdir_does_not_escape_session(self):
        event=prepare_event('codex','PostToolUse',{'cwd':str(self.a),'session_id':'s','tool_input':{'workdir':str(self.a)},'tool_response':'session tool'})
        record_event(self.mem,event)
        self.assertEqual(self.mem.status(event['memory_scope'])['scope'],'session')
        self.assertEqual(self.mem.search(str(self.a),'tool')['entries'],[])

    def test_no_cwd_hooks_resume_and_replay(self):
        for host in ('claude','codex'):
            result=hook(host,'SessionStart',{'session_id':'no-folder'},self.home)
            self.assertIn('LOCAL SESSION MEMORY',result['hookSpecificOutput']['additionalContext'])
        for host in ('claude','codex'):
            event=prepare_event(host,'Stop',{'session_id':'no-folder','last_assistant_message':'saved nofolder'})
            write_json_atomic(self.home/'pending'/(host+'.json'),event)
        self.assertEqual(replay(self.mem),2)
        for host in ('claude','codex'):
            ref=scope_args(None,'no-folder',host)
            self.assertEqual(len(self.mem.search(ref,'nofolder')['entries']),1)

    def test_legacy_journal_retains_folder_scope(self):
        event=prepare_event('claude','Stop',{'cwd':str(self.a),'session_id':'legacy','last_assistant_message':'legacy record'})
        del event['memory_scope']
        record_event(self.mem,event)
        self.assertEqual(len(self.mem.search(str(self.a),'legacy')['entries']),1)

    def test_invalid_scope_refused(self):
        for args in ({},{'session_id':'x'},{'platform':'claude'},
                     {'platform':'claude','session_id':' '},
                     {'platform':'other','session_id':'x'},
                     {'platform':'codex','session_id':'x','scope':'project'},
                     {'cwd':str(self.a),'scope':'session'},
                     {'cwd':str(self.a),'scope':'unknown'}):
            with self.subTest(args=args):
                with self.assertRaises(ValueError):dispatch(self.mem,'project_memory_context',args)

    def test_mcp_session_scope_end_to_end(self):
        ref={'session_id':'mcp-session','platform':'codex','scope':'session'}
        calls=[('project_memory_remember',{**ref,'title':'Session MCP','text':'silver badger','kind':'fact','request_id':'session-mcp'}),
               ('project_memory_search',{**ref,'query':'badger'}),
               ('project_memory_search',{**ref,'session_id':'different','query':'badger'}),
               ('project_memory_context',ref),('project_memory_status',ref)]
        requests=[{'jsonrpc':'2.0','id':0,'method':'tools/list'}]+[
            {'jsonrpc':'2.0','id':i+1,'method':'tools/call','params':{'name':n,'arguments':a}} for i,(n,a) in enumerate(calls)]
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('memory.py')),'--home',str(self.home),'serve'],input='\n'.join(json.dumps(r) for r in requests)+'\n',capture_output=True,text=True,encoding='utf8',timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        replies=[json.loads(line)['result'] for line in proc.stdout.splitlines()]
        self.assertEqual(len(replies),6)
        for tool in replies[0]['tools']:
            self.assertNotIn('cwd',tool['inputSchema']['required'])
            self.assertIn('session_id',tool['inputSchema']['properties'])
        for reply in replies[1:]:self.assertFalse(reply.get('isError'),reply)
        values=[json.loads(r['content'][0]['text']) for r in replies[1:]]
        self.assertEqual(values[1]['entries'][0]['body'],'silver badger')
        self.assertEqual(values[2]['entries'],[])
        self.assertIn('silver badger',values[3]['context'])
        self.assertEqual(values[4]['scope'],'session')

    def test_mcp_roundtrip_and_foreign_read(self):
        entry=self.mem.remember(str(self.a),'From MCP','needle')
        requests=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
                  {'jsonrpc':'2.0','method':'notifications/initialized'},
                  {'jsonrpc':'2.0','id':2,'method':'tools/list'},
                  {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'project_memory_search','arguments':{'cwd':str(self.a),'query':'needle'}}},
                  {'jsonrpc':'2.0','id':4,'method':'tools/call','params':{'name':'project_memory_read','arguments':{'cwd':str(self.b),'ids':[entry['id']]}}}]
        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('memory.py')),'--home',str(self.home),'serve'],input='\n'.join(json.dumps(r) for r in requests)+'\n',capture_output=True,text=True,encoding='utf8',timeout=10)
        self.assertEqual(proc.returncode,0,proc.stderr)
        replies=[json.loads(line) for line in proc.stdout.splitlines()]
        self.assertEqual(len(replies),4);self.assertEqual(len(replies[1]['result']['tools']),5)
        self.assertIn('needle',replies[2]['result']['content'][0]['text'])
        self.assertTrue(replies[3]['result']['isError'])

    def test_import_backup_retry_quarantine(self):
        src=self.base/'old.sqlite3'
        with contextlib.closing(sqlite3.connect(src)) as c:
            c.executescript('''CREATE TABLE sdk_sessions(id INTEGER,project TEXT);
              CREATE TABLE observations(id INTEGER,project TEXT,title TEXT,narrative TEXT,created_at TEXT);
              CREATE TABLE session_summaries(id INTEGER,project TEXT,request TEXT,created_at TEXT);
              CREATE TABLE user_prompts(id INTEGER,session_db_id INTEGER,prompt_text TEXT,created_at TEXT);
              CREATE TABLE tool_uses(id INTEGER,project TEXT,tool_name TEXT,tool_input TEXT,tool_response TEXT,created_at TEXT);
              INSERT INTO sdk_sessions VALUES(1,'old-a');INSERT INTO sdk_sessions VALUES(2,'www');
              INSERT INTO observations VALUES(1,'old-a','Dragon','historical decision','2026-01-01');
              INSERT INTO observations VALUES(2,'www','Other','DO_NOT_MIX','2026-01-01');
              INSERT INTO user_prompts VALUES(1,1,'prompt','2026-01-01');''')
        before=src.read_bytes()
        a=migrate(src,self.home,{'old-a':str(self.a)})
        b=migrate(src,self.home,{'old-a':str(self.a)})
        self.assertEqual(src.read_bytes(),before)
        self.assertEqual(a['counts'],b['verified'])
        self.assertTrue(Path(a['source_snapshot']).exists())
        self.assertEqual(self.mem.search(str(self.a),'DO_NOT_MIX')['entries'],[])
        self.assertEqual(len(self.mem.search(str(self.a),'Dragon')['entries']),1)

    def test_installer_preserves_existing_hooks_and_rolls_back(self):
        user=self.base/'user';(user/'.claude').mkdir(parents=True);(user/'.codex').mkdir()
        settings={'hooks':{'Stop':[{'hooks':[{'type':'command','command':'existing-hook'}]}]},'enabledPlugins':{'old':True}}
        original=json.dumps(settings)
        (user/'.claude/settings.json').write_text(original,encoding='utf8')
        (user/'.codex/config.toml').write_text('model = "existing"\n',encoding='utf8')
        report=setup(self.base/'installed',user)
        current=json.loads((user/'.claude/settings.json').read_text(encoding='utf8'))
        self.assertEqual(current['hooks']['Stop'][0],settings['hooks']['Stop'][0])
        self.assertEqual(current['enabledPlugins'],settings['enabledPlugins'])
        self.assertEqual(len(current['hooks']['Stop']),2)
        manifest=next((self.base/'installed/config-backups').glob('*/manifest.json'))
        rollback(manifest)
        self.assertEqual((user/'.claude/settings.json').read_text(encoding='utf8'),original)
        self.assertFalse((user/'.claude.json').exists())

    def test_installer_collision_does_not_change_other_config(self):
        user=self.base/'user';(user/'.claude').mkdir(parents=True)
        path=user/'.claude/settings.json';path.write_text('{}',encoding='utf8')
        (user/'.claude.json').write_text(json.dumps({'mcpServers':{'project-memory':{'command':'other'}}}),encoding='utf8')
        with self.assertRaises(ValueError):setup(self.base/'installed',user)
        self.assertEqual(path.read_text(encoding='utf8'),'{}')

    @unittest.skipUnless(os.name=='nt','Windows installed hook command')
    def test_installed_hook_runs_with_spaces_and_reinstall_no_duplicates(self):
        user=self.base/'user space';home=self.base/'installed space'
        setup(home,user);setup(home,user)
        cfg=json.loads((user/'.claude/settings.json').read_text(encoding='utf8'))
        self.assertEqual(len(cfg['hooks']['SessionStart']),1)
        command=cfg['hooks']['SessionStart'][0]['hooks'][0]['command']
        result=subprocess.run(command,shell=True,input=json.dumps({'cwd':str(self.a),'session_id':'native-hook'}),capture_output=True,text=True,encoding='utf8',timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['hookSpecificOutput']['hookEventName'],'SessionStart')
        with contextlib.closing(Memory(home)) as m:self.assertEqual(m.db.execute('SELECT count(*) FROM entries').fetchone()[0],1)

if __name__=='__main__':unittest.main(verbosity=2)
