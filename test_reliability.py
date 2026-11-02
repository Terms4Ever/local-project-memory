"""Synthetic proofs for the failures observed on 28 October 2026."""
import contextlib
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

import memory
import reconcile
import search_index


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.cwd=self.root/'project';self.cwd.mkdir();self.home=self.root/'state'
        self.mem=memory.Memory(self.home);self.mem.register(str(self.cwd))
        self.scope=memory.scope_args(str(self.cwd),'synthetic-session','claude')

    def tearDown(self):self.mem.close();self.tmp.cleanup()

    def test_long_current_note_is_complete_even_with_old_keyword_match(self):
        self.mem.remember(self.scope,'Old Claude setup','Claude installation instructions')
        text='Current decision. '+('Useful detail. '*199)+'REQUIRED_TAIL'
        row=self.mem.remember(self.scope,'Current work',text,kind='handoff')
        context=self.mem.context(self.scope,'Claude')
        selected=[json.loads(x) for x in context.splitlines() if x.startswith('{"id":')]
        chosen=next(x for x in selected if x['id']==row['id'])
        self.assertEqual(chosen['content'],text);self.assertFalse(chosen['excerpt'])
        self.assertLessEqual(len(json.dumps(context,ensure_ascii=False).encode()),6000)

    def work_turn(self,host='claude',sid='synthetic-session',event_id='prompt-one'):
        data={'cwd':str(self.cwd),'session_id':sid}
        memory.hook(host,'UserPromptSubmit',data|{'prompt':'Implement the approved feature','event_id':event_id},self.home)
        memory.hook(host,'PostToolUse',data|{'tool_name':'Bash','tool_input':{'command':'test'},'tool_use_id':event_id+'-tool'},self.home)
        return data|{'last_assistant_message':'Implemented and verified. '+('Specific evidence. '*20)}

    def test_claude_stop_requests_note_once_and_confirms_actual_write(self):
        data=self.work_turn()
        result=memory.hook('claude','Stop',data,self.home)
        self.assertEqual(result['decision'],'block');self.assertIn('project_memory_remember',result['reason'])
        self.mem.remember(self.scope,'Verified handoff','Evidence and next steps',kind='handoff')
        self.assertEqual(memory.hook('claude','Stop',data|{'stop_hook_active':True},self.home),{})
        self.assertEqual(self.mem.status()['handoff_checks'],{'saved':1})

    def test_stop_does_not_loop_or_claim_failed_note_saved(self):
        data=self.work_turn();memory.hook('claude','Stop',data,self.home)
        self.assertEqual(memory.hook('claude','Stop',data,self.home),{})
        self.assertEqual(self.mem.status()['handoff_checks'],{'not_confirmed':1})

    def test_foreign_note_does_not_satisfy_stop_and_new_turn_can_request_again(self):
        data=self.work_turn()
        self.mem.remember({**self.scope,'session_id':'foreign'},'Other task','Unrelated',kind='handoff')
        self.assertEqual(memory.hook('claude','Stop',data,self.home)['decision'],'block')
        data=self.work_turn(event_id='prompt-two')
        self.assertEqual(memory.hook('claude','Stop',data,self.home)['decision'],'block')

    def test_stop_skips_codex_background_and_existing_continuation(self):
        data=self.work_turn(host='codex');self.assertEqual(memory.hook('codex','Stop',data,self.home),{})
        data=self.work_turn()
        self.assertEqual(memory.hook('claude','Stop',data|{'stop_hook_active':True},self.home),{})
        self.assertEqual(memory.hook('claude','Stop',data|{'last_assistant_message':''},self.home),{})

    def test_saved_receipt_survives_later_tools_and_reports_staleness_separately(self):
        data=self.work_turn();memory.hook('claude','Stop',data,self.home)
        self.mem.remember(self.scope,'Checkpoint','Actually written',kind='handoff')
        memory.hook('claude','PostToolUse',data|{'tool_name':'Write','tool_use_id':'after-note'},self.home)
        self.assertEqual(memory.hook('claude','Stop',data|{'stop_hook_active':True},self.home),{})
        state=self.mem.status()
        self.assertEqual(state['handoff_checks'],{'saved':1})
        self.assertFalse(state['handoff_sessions'][0]['fresh'])
        self.assertEqual(state['handoff_sessions'][0]['reason'],'continuation_guard')

    def test_receipt_confirmed_without_followup_stop_and_after_new_prompt(self):
        data=self.work_turn();result=memory.hook('claude','Stop',data,self.home)
        args=json.JSONDecoder().raw_decode(result['reason'].split('doplň text: ',1)[1])[0]
        self.work_turn(event_id='new-request')
        row=memory.dispatch(self.mem,'project_memory_remember',args|{'text':'Delayed write from previous request'})
        self.assertEqual(self.mem.status()['handoff_checks'],{'saved':1})
        import memory_use
        self.assertEqual(memory_use.repair_receipts(self.mem,memory),1)
        self.assertEqual(memory_use.repair_receipts(self.mem,memory),0)
        marker=next((self.home/'handoff-checks').glob('*.json'))
        self.assertEqual(json.loads(marker.read_text())['note_id'],row['id'])

    def test_legacy_receipt_recovers_superseded_note_without_rewriting_it(self):
        import memory_use
        row=self.mem.remember(self.scope,'Original','Preserved',kind='handoff',request_id='handoff:legacy')
        self.mem.remember(self.scope,'Replacement','Newer',kind='handoff',supersedes=row['id'])
        p=self.home/'handoff-checks/legacy.json'
        memory.write_json_atomic(p,{'state':'not_confirmed','session_id':self.scope['session_id'],'project_id':row['project_id']})
        self.assertEqual(memory_use.repair_receipts(self.mem,memory),1)
        restored=self.mem.db.execute('SELECT body,state FROM entries WHERE id=?',(row['id'],)).fetchone()
        self.assertEqual(tuple(restored),('Preserved','superseded'))
        self.assertEqual(json.loads(p.read_text())['state'],'saved')

    def test_background_work_gets_checkpoint_and_recent_checkpoint_is_rate_limited(self):
        data=self.work_turn()|{'background_tasks':[{'status':'running'}],'session_crons':[{'id':'pending'}]}
        self.assertEqual(memory.hook('claude','Stop',data,self.home)['decision'],'block')
        row=self.mem.remember(self.scope,'In progress','Work still running',kind='handoff')
        self.assertEqual(memory.hook('claude','Stop',data|{'stop_hook_active':True},self.home),{})
        newer=self.work_turn(event_id='background-completion')|{'background_tasks':[{'status':'running'}]}
        self.assertEqual(memory.hook('claude','Stop',newer,self.home),{})
        self.assertEqual(self.mem.status()['handoff_sessions'][0]['reason'],'recent_background_checkpoint')
        import datetime as dt
        old=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=11)).isoformat()
        self.mem.db.execute('UPDATE entries SET created_at=? WHERE id=?',(old,row['id']))
        self.assertEqual(memory.hook('claude','Stop',newer,self.home)['decision'],'block')
        self.assertEqual(memory.hook('claude','Stop',newer,self.home),{})

    def test_many_notifications_create_new_batch_but_not_a_stop_loop(self):
        data=self.work_turn();memory.hook('claude','Stop',data,self.home)
        self.mem.remember(self.scope,'Checkpoint','Previous work',kind='handoff')
        for i in range(25):
            memory.hook('claude','UserPromptSubmit',data|{'prompt':'<task-notification>done</task-notification>','event_id':'notification-'+str(i)},self.home)
        memory.hook('claude','PostToolUse',data|{'tool_name':'Read','tool_use_id':'new-evidence'},self.home)
        self.assertEqual(memory.hook('claude','Stop',data,self.home)['decision'],'block')
        self.assertEqual(memory.hook('claude','Stop',data,self.home),{})

    def test_stop_skip_conditions_are_observable_without_private_task_text(self):
        data={'session_id':'no-prompt','last_assistant_message':'Done','background_tasks':[{'description':'DO_NOT_COPY'}],'stop_hook_active':True}
        self.assertEqual(memory.hook('claude','Stop',data,self.home),{})
        state=self.mem.status()['handoff_sessions'][0]
        self.assertEqual(state['reason'],'missing_prompt');self.assertEqual(state['background_tasks'],1)
        self.assertNotIn('DO_NOT_COPY',json.dumps(state))
        raw=self.mem.db.execute("SELECT body FROM entries WHERE title='Stop' ORDER BY id DESC LIMIT 1").fetchone()[0]
        self.assertNotIn('DO_NOT_COPY',raw)
        self.assertTrue(json.loads(raw)['memory_stop_conditions']['stop_hook_active'])

    def test_folderless_stop_uses_session_and_ignores_other_host(self):
        data={'session_id':'folderless'}
        memory.hook('claude','UserPromptSubmit',data|{'prompt':'Investigate failure'},self.home)
        memory.hook('claude','PostToolUseFailure',data|{'tool_name':'Bash','tool_use_id':'failed-test','error':'Failed'},self.home)
        self.mem.remember(memory.scope_args(None,'folderless','codex'),'Other host','Unrelated',kind='handoff')
        result=memory.hook('claude','Stop',data|{'last_assistant_message':'Test failed.'},self.home)
        self.assertEqual(result['decision'],'block')
        self.assertIn('"session_id": "folderless"',result['reason'])
        self.assertIn('"platform": "claude"',result['reason'])
        self.mem.remember(memory.scope_args(None,'folderless','claude'),'Failure','Test failed, investigate',kind='handoff')
        self.assertEqual(memory.hook('claude','Stop',data|{'last_assistant_message':'Saved','stop_hook_active':True},self.home),{})
        self.assertEqual(self.mem.status()['handoff_checks'],{'saved':1})

    def test_stale_note_does_not_satisfy_stop_and_only_own_handoff_is_replaced(self):
        old=self.mem.remember(self.scope,'Own handoff','Old task',kind='handoff')
        foreign=self.mem.remember({**self.scope,'session_id':'other'},'Other handoff','Other task',kind='handoff')
        data=self.work_turn()
        result=memory.hook('claude','Stop',data,self.home)
        self.assertIn('"supersedes": '+str(old['id']),result['reason'])
        self.assertNotIn('"supersedes": '+str(foreign['id']),result['reason'])

    def test_own_handoff_precedes_other_session_but_old_fact_does_not_hide_latest(self):
        self.mem.remember(self.scope,'Old fact','Old fact',kind='fact')
        foreign=self.mem.remember({**self.scope,'session_id':'other'},'Shared decision','Shared new decision',kind='decision')
        rows=lambda:[json.loads(x) for x in self.mem.context(self.scope).splitlines() if x.startswith('{"id":')]
        self.assertEqual(rows()[0]['id'],foreign['id'])
        self.work_turn()
        own=self.mem.remember(self.scope,'Own handoff','OWN_NEXT_STEP',kind='handoff')
        self.mem.remember({**self.scope,'session_id':'other'},'Other handoff','OTHER_NEXT_STEP',kind='handoff')
        self.assertEqual(rows()[0]['id'],own['id'])

    def test_old_own_handoff_cannot_displace_new_project_state(self):
        self.mem.remember(self.scope,'Old task','Old task',kind='handoff')
        self.work_turn()
        text='New current state. '+('Complete explanation. '*125)+'MANDATORY_TAIL'
        new=self.mem.remember({**self.scope,'session_id':'other'},'New shared state',text,kind='handoff')
        rows=[json.loads(x) for x in self.mem.context(self.scope).splitlines() if x.startswith('{"id":')]
        self.assertEqual(rows[0]['id'],new['id'])
        self.assertEqual(rows[0]['content'],text)

    def test_three_real_argument_shapes_are_accepted_without_guessing_scope(self):
        for wrapper in [{'scope':json.dumps(self.scope)},{'MEMORY_SCOPE':self.scope},self.scope]:
            args={**wrapper,'kind':'decision','title':'Approved','content':'Exact complete decision.'}
            row=memory.dispatch(self.mem,'project_memory_remember',args)
            self.assertEqual(row['project_id'],self.mem.resolve(self.scope)['id'])
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE source='note'").fetchone()[0],1)
        self.assertEqual(self.mem.status()['unresolved_diagnostics'],[])

    def test_conflicting_wrappers_are_rejected_and_visible(self):
        other=self.root/'other';other.mkdir()
        with self.assertRaisesRegex(ValueError,'Conflicting'):
            memory.dispatch(self.mem,'project_memory_remember',{'MEMORY_SCOPE':self.scope,'cwd':str(other),'title':'X','text':'Y'})
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],0)
        self.assertEqual(len(self.mem.status()['unresolved_diagnostics']),1)

    def test_missing_note_text_has_actionable_error_without_saving_secrets(self):
        with self.assertRaisesRegex(ValueError,'title and text strings'):
            memory.dispatch(self.mem,'project_memory_remember',{**self.scope,'title':'SECRET_TITLE_DO_NOT_LOG','password':'NEVER_LOG_ME'})
        errors=json.dumps(self.mem.status()['unresolved_diagnostics'])
        self.assertNotIn('NEVER_LOG_ME',errors);self.assertNotIn('SECRET_TITLE_DO_NOT_LOG',errors)

    def test_full_decision_tail_and_own_task_survive_other_sessions(self):
        text='Exact project decision. '+('Useful explanation. '*55)+'CRITICAL_TAIL_REQUIREMENT'
        note=self.mem.remember(self.scope,'Decision',text,kind='decision')
        memory.hook('claude','Stop',{'cwd':str(self.cwd),'session_id':'synthetic-session','last_assistant_message':'OWN_TASK_NEXT_STEP'},self.home)
        memory.hook('claude','Stop',{'cwd':str(self.cwd),'session_id':'other-session','last_assistant_message':'UNRELATED_OTHER_TASK'},self.home)
        context=self.mem.context(self.scope,'decision')
        self.assertIn('CRITICAL_TAIL_REQUIREMENT',context);self.assertIn('OWN_TASK_NEXT_STEP',context)
        self.assertNotIn('UNRELATED_OTHER_TASK',context)
        rows=[json.loads(line) for line in context.splitlines() if line.startswith('{"id":')]
        self.assertFalse(next(row for row in rows if row['id']==note['id'])['excerpt'])
        self.assertLessEqual(len(context),memory.MAX_CONTEXT_CHARS)
        self.assertLessEqual(len(json.dumps(context,ensure_ascii=False).encode()),memory.MAX_CONTEXT_BYTES)

    def legacy(self):
        folder=self.root/'old';folder.mkdir()
        with contextlib.closing(sqlite3.connect(folder/'memory.sqlite3')) as db:db.executescript(memory.SCHEMA)
        return memory.Memory(folder)

    def test_index_migration_preserves_all_original_bytes_and_ids(self):
        with contextlib.closing(self.legacy()) as mem:
            body='Before data:image/png;base64,'+'ABcd0123/'*9000+' AFTER_TAIL_SEARCH'
            row=mem.remember(str(self.cwd),'Image proof',body)
            before=dict(mem.db.execute('SELECT * FROM entries WHERE id=?',(row['id'],)).fetchone())
            search_index.optimize(mem.db)
            after=dict(mem.db.execute('SELECT * FROM entries WHERE id=?',(row['id'],)).fetchone())
            self.assertEqual(before,after)
            projection=mem.db.execute('SELECT * FROM search_documents WHERE entry_id=?',(row['id'],)).fetchone()
            self.assertLess(len(projection['body']),200)
            self.assertEqual(projection['body_sha256'],hashlib.sha256(body.encode()).hexdigest())
            self.assertEqual(mem.search(str(self.cwd),'AFTER_TAIL_SEARCH')['entries'][0]['id'],row['id'])
            self.assertEqual(mem.db.execute('PRAGMA user_version').fetchone()[0],3)
            mem.db.execute("INSERT INTO entries_fts(entries_fts,rank) VALUES('integrity-check',1)")

    def test_interrupted_index_build_resumes_and_sees_old_writer_updates(self):
        with contextlib.closing(self.legacy()) as mem:
            rows=[mem.remember(str(self.cwd),'Title '+str(i),'originalword'+str(i)) for i in range(3)]
            def interrupt(state):raise RuntimeError('simulated interruption')
            with self.assertRaisesRegex(RuntimeError,'interruption'):search_index.optimize(mem.db,interrupt,batch=1)
            self.assertEqual(mem.search(str(self.cwd),'originalword2')['entries'][0]['id'],rows[2]['id'])
            # An existing 1.3.x connection has only ordinary SQLite triggers.
            with contextlib.closing(sqlite3.connect(mem.db_path,isolation_level=None)) as old:
                old.execute('UPDATE entries SET body=? WHERE id=?',('changedbyoldwriter',rows[0]['id']))
            search_index.optimize(mem.db,batch=1)
            self.assertEqual(mem.search(str(self.cwd),'changedbyoldwriter')['entries'][0]['id'],rows[0]['id'])
            self.assertEqual(mem.search(str(self.cwd),'originalword0')['entries'],[])
            with contextlib.closing(sqlite3.connect(mem.db_path,isolation_level=None)) as old:
                old.execute('UPDATE entries SET body=? WHERE id=?',('oldwriterafterswap',rows[1]['id']))
            self.assertEqual(mem.search(str(self.cwd),'oldwriterafterswap')['entries'][0]['id'],rows[1]['id'])
            self.assertEqual(search_index.state(mem.db)['stage'],'ready')

    def transcript(self,lines,name='claude.jsonl'):
        path=self.root/name
        path.write_text(''.join(json.dumps(line)+'\n' for line in lines),encoding='utf8')
        return path

    def test_explicit_rollback_keeps_new_data_and_can_migrate_again(self):
        new=self.mem.remember(self.scope,'New data','savedafterupgrade')
        search_index.rollback(self.mem.db)
        self.assertEqual(self.mem.search(self.scope,'savedafterupgrade')['entries'][0]['id'],new['id'])
        self.mem.db.execute('UPDATE entries SET body=? WHERE id=?',('writtenafterrollback',new['id']))
        self.assertEqual(self.mem.search(self.scope,'writtenafterrollback')['entries'][0]['id'],new['id'])
        search_index.optimize(self.mem.db)
        self.assertEqual(self.mem.search(self.scope,'writtenafterrollback')['entries'][0]['id'],new['id'])

    def claude_pair(self,tool_id='tool-1',name='Bash',args=None,error=False,timestamp='2026-10-28T10:00:00Z'):
        meta={'sessionId':'synthetic-session','cwd':str(self.cwd),'timestamp':timestamp}
        return [{**meta,'type':'assistant','message':{'content':[{'type':'tool_use','id':tool_id,'name':name,'input':args or {'command':'synthetic harmless command'}}]}},
                {**meta,'type':'user','message':{'content':[{'type':'tool_result','tool_use_id':tool_id,'content':'COMPLETE_RECOVERED_RESULT','is_error':error}]}}]

    def scan(self,path,platform='claude',sid='synthetic-session'):
        return reconcile.scan(self.mem,memory,path,platform,sid,'2026-10-26',seconds=10)

    def test_missing_completed_event_recovers_once_with_full_result(self):
        path=self.transcript(self.claude_pair())
        self.assertEqual(self.scan(path)['recovered'],1)
        self.assertEqual(self.scan(path)['recovered'],0)
        row=self.mem.db.execute("SELECT * FROM entries WHERE source='transcript'").fetchone()
        self.assertIn('COMPLETE_RECOVERED_RESULT',row['body'])
        self.assertEqual(row['project_id'],self.mem.resolve(self.scope)['id'])

    def test_native_event_is_not_duplicated_and_late_hook_supersedes_recovery(self):
        path=self.transcript(self.claude_pair());self.scan(path)
        native=memory.prepare_event('claude','PostToolUse',{'cwd':str(self.cwd),'session_id':'synthetic-session','tool_use_id':'tool-1','tool_name':'Bash','tool_input':{'command':'original'},'tool_response':'native representation'})
        memory.record_event(self.mem,native)
        self.assertEqual(self.mem.db.execute("SELECT state FROM entries WHERE source='transcript'").fetchone()[0],'superseded')
        another=self.transcript(self.claude_pair(),name='second.jsonl');self.scan(another)
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE source='transcript'").fetchone()[0],1)

    def test_failed_notes_recover_with_historical_date_and_idempotency(self):
        args={'MEMORY_SCOPE':self.scope,'title':'Historical decision','content':'Full lost note','kind':'decision'}
        path=self.transcript(self.claude_pair(name='mcp__project-memory__project_memory_remember',args=args,error=True))
        self.assertEqual(self.scan(path)['recovered'],1);self.scan(path)
        row=self.mem.db.execute("SELECT * FROM entries WHERE source='note'").fetchone()
        self.assertEqual(row['created_at'],'2026-10-28T10:00:00Z');self.assertIn('Full lost note',row['body'])
        self.assertEqual(self.mem.status()['unresolved_diagnostics'],[])

    def test_current_note_is_not_replaced_by_recovered_old_attempt(self):
        current=self.mem.remember(self.scope,'Decision','CURRENT authoritative note')
        path=self.transcript(self.claude_pair(name='project_memory_remember',args={**self.scope,'title':'Decision','text':'OLD attempt'},error=True))
        self.scan(path)
        self.assertEqual(self.mem.db.execute('SELECT state FROM entries WHERE id=?',(current['id'],)).fetchone()[0],'active')
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE source='note' AND state='active'").fetchone()[0],1)

    def test_partial_line_waits_and_failed_recovery_is_preserved(self):
        lines=self.claude_pair();path=self.transcript(lines[:1]);tail=json.dumps(lines[1])
        with path.open('a',encoding='utf8') as f:f.write(tail[:80])
        self.assertFalse(self.scan(path)['complete'])
        with path.open('a',encoding='utf8') as f:f.write(tail[80:]+'\n')
        self.assertEqual(self.scan(path)['recovered'],1)
        wrong={**self.scope,'cwd':str(self.root/'absent'),'title':'Note','text':'Data'}
        bad=self.transcript(self.claude_pair('bad-note','project_memory_remember',wrong,True),name='bad.jsonl')
        self.scan(bad)
        self.assertEqual(len(list((self.home/'transcript-retry').glob('*.json'))),1)
        self.assertTrue(self.mem.status()['unresolved_diagnostics'])

    def test_foreign_inherited_session_is_not_imported(self):
        path=self.transcript(self.claude_pair())
        self.assertEqual(self.scan(path,sid='different-session')['recovered'],0)
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],0)

    def test_claude_fork_rewritten_session_does_not_duplicate_native_event(self):
        ident='toolu_'+('A'*24)
        native=memory.prepare_event('claude','PostToolUse',{'cwd':str(self.cwd),'session_id':'parent-session','tool_use_id':ident,'tool_name':'Bash','tool_input':{'command':'synthetic'}})
        memory.record_event(self.mem,native)
        path=self.transcript(self.claude_pair(tool_id=ident))
        self.assertEqual(self.scan(path)['recovered'],0)
        # The same string in a different project is not sufficient to merge it.
        other=self.root/'separate';other.mkdir();self.mem.register(str(other))
        call={'platform':'claude','sid':'different','cwd':str(other),'id':ident,'name':'Bash','input':{},'timestamp':'2026-10-28T10:00:00Z'}
        self.assertEqual(reconcile.recover_tool(self.mem,memory,call,'different project'),1)

    def test_claude_fork_note_and_late_native_event_have_one_active_copy(self):
        ident='toolu_'+('B'*24);args={**self.scope,'title':'Decision','text':'Complete note'}
        self.scan(self.transcript(self.claude_pair(ident,'project_memory_remember',args,True)))
        other_scope={**self.scope,'session_id':'fork-session'}
        self.assertEqual(reconcile.recover_note(self.mem,memory,'claude','fork-session',str(self.cwd),ident,other_scope|{'title':'Decision','text':'Complete note'},'2026-10-28T10:00:00Z'),0)
        tool='toolu_'+('C'*24)
        self.scan(self.transcript(self.claude_pair(tool),name='late.jsonl'))
        native=memory.prepare_event('claude','PostToolUse',{'cwd':str(self.cwd),'session_id':'parent-session','tool_use_id':tool,'tool_name':'Bash','tool_input':{}})
        memory.record_event(self.mem,native);reconcile.supersede_fork_copies(self.mem)
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE source='transcript' AND state='active'").fetchone()[0],0)

    def test_removed_directory_requires_exact_recorded_scope(self):
        child=self.cwd/'scratch';child.mkdir()
        native=memory.prepare_event('claude','PostToolUse',{'cwd':str(child),'session_id':'synthetic-session','tool_name':'Bash','tool_use_id':'earlier','tool_input':{'command':'previous'}})
        memory.record_event(self.mem,native);child.rmdir()
        call={'platform':'claude','sid':'synthetic-session','cwd':str(child),'id':'missing','name':'Bash','input':{'command':'completed'},'timestamp':'2026-10-28T10:00:00Z'}
        self.assertEqual(reconcile.recover_tool(self.mem,memory,call,'finished'),1)
        row=self.mem.db.execute("SELECT * FROM entries WHERE source='transcript'").fetchone()
        self.assertEqual(row['project_id'],self.mem.resolve(self.scope)['id'])
        with self.assertRaisesRegex(ValueError,'no unique recorded'):
            reconcile.recover_tool(self.mem,memory,{**call,'id':'foreign','sid':'other-session'},'must not infer')

    def test_codex_completed_command_uses_actual_directory_and_id(self):
        other=self.root/'second';other.mkdir();self.mem.register(str(other))
        path=self.transcript([
            {'type':'session_meta','payload':{'id':'synthetic-session','cwd':str(self.cwd)}},
            {'type':'event_msg','timestamp':'2026-10-28T10:00:00Z','payload':{'type':'item_completed','thread_id':'synthetic-session','item':{
                'type':'CommandExecution','id':'exec-synthetic','command':['python','example.py'],'cwd':other.as_uri(),'aggregated_output':'CODEx_FULL_RESULT','exit_code':0}}}],name='codex.jsonl')
        self.assertEqual(self.scan(path,platform='codex')['recovered'],1)
        row=self.mem.db.execute("SELECT * FROM entries WHERE source='transcript'").fetchone()
        self.assertEqual(row['project_id'],self.mem.resolve(str(other))['id'])
        self.assertIn('CODEx_FULL_RESULT',row['body'])

    def test_codex_child_uses_explicit_root_and_skips_inherited_events(self):
        def completed(thread,ident):
            return {'type':'event_msg','timestamp':'2026-10-28T10:00:00Z','payload':{'type':'item_completed','thread_id':thread,'item':{
                'type':'CommandExecution','id':ident,'command':['synthetic'],'cwd':str(self.cwd),'aggregated_output':'result','exit_code':0}}}
        native=memory.prepare_event('codex','PostToolUse',{'cwd':str(self.cwd),'session_id':'root-session','tool_use_id':'already-saved','tool_name':'Bash','tool_input':{'command':'synthetic'}})
        memory.record_event(self.mem,native)
        path=self.transcript([
            {'type':'session_meta','payload':{'id':'child-session','cwd':str(self.cwd),'source':{'subagent':{'thread_spawn':{'parent_thread_id':'root-session'}}}}},
            {'type':'session_meta','payload':{'id':'root-session','cwd':str(self.cwd),'source':'vscode'}},
            completed('root-session','inherited'),completed('child-session','already-saved'),completed('child-session','missing-child')],name='child.jsonl')
        self.assertEqual(self.scan(path,platform='codex',sid='child-session')['recovered'],1)
        row=self.mem.db.execute("SELECT * FROM entries WHERE source='transcript'").fetchone()
        self.assertEqual(row['session_id'],'root-session');self.assertTrue(row['source_key'].endswith(':missing-child'))
        with path.open('a',encoding='utf8') as f:f.write(json.dumps(completed('child-session','next-child'))+'\n')
        self.assertEqual(self.scan(path,platform='codex',sid='child-session')['recovered'],1)
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE source='transcript' AND session_id='root-session'").fetchone()[0],2)


if __name__=='__main__':unittest.main(verbosity=2)
