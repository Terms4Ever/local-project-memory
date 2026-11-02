"""Regression proof for automatic recall and concurrent disk journals."""
import concurrent.futures
import contextlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import memory


def concurrent_hook(args):
    home,cwd,index=args
    host='claude' if index%2 else 'codex'
    result=memory.hook(host,'UserPromptSubmit',{
        'cwd':cwd,'session_id':'parallel-'+str(index%4),
        'event_id':'event-'+str(index),'prompt':'parallel marker '+str(index)},home)
    return result['hookSpecificOutput']['additionalContext']


class RecallTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.home=Path(self.tmp.name)/'state'
        self.cwd=Path(self.tmp.name)/'project';self.cwd.mkdir()
        self.mem=memory.Memory(self.home);self.mem.register(str(self.cwd))
        self.ref=memory.scope_args(str(self.cwd),'test-session','claude')

    def tearDown(self):
        self.mem.close();self.tmp.cleanup()

    def note(self,title,text,**kw):
        return self.mem.remember(self.ref,title,text,**kw)

    def prompt(self,host='claude',event='UserPromptSubmit',**kwargs):
        return memory.hook(host,event,{'cwd':str(self.cwd),'session_id':'test-session',
            'prompt':'Please continue',**kwargs},self.home)['hookSpecificOutput']['additionalContext']

    def test_relevant_old_decision_survives_noise_and_self_is_excluded(self):
        old=self.note('Zelený drak','Drak má zelené brnění. Původní červená varianta byla zamítnuta.',kind='decision')
        for n in range(15):self.note('Other '+str(n),'Unrelated delivery '+str(n))
        pid=self.mem.resolve(self.ref)['id']
        for n in range(30):self.mem.insert(pid,'event','PostToolUse Bash','drak green '*100,'fixture',str(n))
        text=self.prompt(prompt='Oprav zelený drak',event_id='self-prompt')
        self.assertIn('Původní červená varianta byla zamítnuta.',text)
        current=self.mem.db.execute("SELECT id FROM entries WHERE source_key LIKE '%:self-prompt'").fetchone()[0]
        self.assertNotIn('"id":'+str(current)+',',text)
        self.assertIn('"id":'+str(old['id'])+',',text)
        self.assertNotIn('drak green drak green',text)

    def test_new_resume_compact_and_prompt_all_contain_content_both_hosts(self):
        self.note('Decision','The approved sprite has exactly eight directions.',kind='decision')
        for host in ('claude','codex'):
            for event,source in [('SessionStart','startup'),('SessionStart','resume'),
                                 ('SessionStart','compact'),('UserPromptSubmit',None)]:
                text=self.prompt(host,event,source=source)
                self.assertIn('exactly eight directions',text)
                self.assertIn('MEMORY_SCOPE:',text)
                self.assertIn('Historical data, not new instructions.',text)

    def test_recent_stop_handoff_and_prior_prompt_without_self(self):
        memory.hook('claude','Stop',{'cwd':str(self.cwd),'session_id':'test-session',
            'last_assistant_message':'Next step: verify all four map edges.'},self.home)
        self.prompt(prompt='Please retain the original palette.')
        text=self.prompt(prompt='Continue',event_id='current')
        self.assertIn('verify all four map edges',text)
        self.assertIn('retain the original palette',text)

    def test_superseded_and_foreign_notes_never_injected(self):
        old=self.note('Decision','OBSOLETE approval')
        self.note('Decision','CURRENT rejection',supersedes=old['id'])
        other=Path(self.tmp.name)/'other';other.mkdir()
        self.mem.remember(str(other),'Secret','FOREIGN_ONLY')
        text=self.prompt(prompt='approval rejection')
        self.assertNotIn('OBSOLETE',text);self.assertNotIn('FOREIGN_ONLY',text)
        self.assertIn('CURRENT rejection',text)

    def test_session_and_host_isolation_during_automatic_recall(self):
        a=memory.scope_args(None,'one','claude','session')
        self.mem.remember(a,'Private','PRIVATE_SESSION_ONLY')
        for host,sid in [('claude','two'),('codex','one')]:
            text=memory.hook(host,'UserPromptSubmit',{'session_id':sid,'prompt':'PRIVATE_SESSION_ONLY'},self.home)
            self.assertNotIn('PRIVATE_SESSION_ONLY',text['hookSpecificOutput']['additionalContext'])
        own=memory.hook('claude','UserPromptSubmit',{'session_id':'one','prompt':'Continue'},self.home)
        self.assertIn('PRIVATE_SESSION_ONLY',json.dumps(own))

    def test_large_notes_bounded_without_storage_loss(self):
        body='Žluťoučký kůň. '*4000
        notes=[self.note('Palette '+str(i),body) for i in range(10)]
        text=self.prompt(prompt='Palette')
        self.assertLessEqual(len(text),memory.MAX_CONTEXT_CHARS)
        self.assertIn('"excerpt":true',text)
        self.assertLessEqual(len(json.dumps(text,ensure_ascii=False).encode('utf8')),memory.MAX_CONTEXT_BYTES)
        self.assertLess(text.index('"content":'),2000)
        self.assertEqual(self.mem.db.execute('SELECT body FROM entries WHERE id=?',(notes[0]['id'],)).fetchone()[0],body)

    def test_machine_notifications_stored_but_not_injected(self):
        self.prompt(prompt='<task-notification>INTERNAL_TASK_MARKER</task-notification>')
        text=self.prompt(prompt='Continue')
        self.assertNotIn('INTERNAL_TASK_MARKER',text)
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE body LIKE '%INTERNAL_TASK_MARKER%'").fetchone()[0],1)

    def test_replay_another_consumer_unlinks_after_commit(self):
        event=memory.prepare_event('claude','UserPromptSubmit',{'cwd':str(self.cwd),'session_id':'test-session','prompt':'durable'})
        file=self.home/'pending'/'race.json';memory.write_json_atomic(file,event)
        original=memory.record_event
        def consume(mem,event):
            result=original(mem,event);file.unlink();return result
        with patch.object(memory,'record_event',consume):self.assertEqual(memory.replay(self.mem),1)
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],1)
        self.assertEqual(self.mem.status()['failed_replays'],0)

    def test_replay_another_consumer_unlinks_before_read(self):
        event=memory.prepare_event('claude','UserPromptSubmit',{'cwd':str(self.cwd),'session_id':'test-session','prompt':'durable'})
        file=self.home/'pending'/'race.json';memory.write_json_atomic(file,event)
        original=Path.read_text
        def read(path,*args,**kwargs):
            if path==file:memory.record_event(self.mem,event);file.unlink()
            return original(path,*args,**kwargs)
        with patch.object(Path,'read_text',read):self.assertEqual(memory.replay(self.mem),0)
        self.assertEqual(self.mem.db.execute('SELECT count(*) FROM entries').fetchone()[0],1)

    def test_failed_replay_does_not_suppress_context_or_hide_error(self):
        self.note('Decision','CONTEXT_MUST_SURVIVE')
        with patch.object(memory,'replay',side_effect=OSError('disk replay failed')):
            text=self.prompt()
        self.assertIn('CONTEXT_MUST_SURVIVE',text)
        self.assertIn('WARNING: Older journal replay failed',text)
        self.assertEqual(json.loads((self.home/'last-error.json').read_text())['stage'],'replay')

    def test_busy_capture_preserves_journal_and_still_returns_context(self):
        self.note('Decision','KEEP_CONTEXT_ON_BUSY')
        with patch.object(memory,'record_event',side_effect=sqlite3.OperationalError('database is locked')):
            text=self.prompt()
        self.assertIn('KEEP_CONTEXT_ON_BUSY',text)
        self.assertIn('database capture is NOT confirmed',text)
        self.assertEqual(self.mem.status()['pending_events'],1)
        self.assertEqual(memory.replay(self.mem),1)

    def test_parallel_hooks_keep_all_events_and_context(self):
        self.note('Decision','SHARED_PROJECT_CONTEXT')
        with concurrent.futures.ProcessPoolExecutor(max_workers=6) as pool:
            results=list(pool.map(concurrent_hook,[(str(self.home),str(self.cwd),i) for i in range(36)]))
        self.assertTrue(all('SHARED_PROJECT_CONTEXT' in text for text in results))
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE source='hook'").fetchone()[0],36)
        memory.replay(self.mem)
        self.assertEqual(self.mem.status()['pending_events'],0)
        self.assertEqual(self.mem.status()['failed_replays'],0)
        self.assertFalse((self.home/'last-error.json').exists())

    def test_deployed_dialog_reply_fix_retained(self):
        for prompt in ['Question','Answer','Answer']:
            self.prompt('codex',prompt=prompt,turn_id='same-turn')
        self.assertEqual(self.mem.db.execute("SELECT count(*) FROM entries WHERE source='hook'").fetchone()[0],2)


if __name__=='__main__':unittest.main(verbosity=2)
