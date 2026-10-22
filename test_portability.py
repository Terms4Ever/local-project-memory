import contextlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from install import setup
from memory import Memory, scope_args
from transfer import inventory, restore

class PortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.old=self.base/'old project';self.new=self.base/'new project'
        self.old.mkdir();self.new.mkdir()
        self.src=self.base/'source';self.dest=self.base/'destination'
        with contextlib.closing(Memory(self.src)) as m:
            self.pid=m.register(str(self.old))['id']
            self.note=m.remember(str(self.old),'Migration note','private maple',request_id='original')
            self.session=scope_args(None,'original-session','claude')
            self.session_note=m.remember(self.session,'Session note','separate kestrel')
            self.snapshot=m.backup()
    def tearDown(self):self.temp.cleanup()

    def test_restore_maps_new_path_and_preserves_session(self):
        before=Path(self.snapshot).read_bytes()
        report=restore(self.snapshot,self.dest,{self.pid:str(self.new)})
        self.assertEqual(report['records'],2)
        self.assertEqual(before,Path(self.snapshot).read_bytes())
        with contextlib.closing(Memory(self.dest)) as m:
            self.assertEqual(m.search(str(self.new),'maple')['entries'][0]['id'],self.note['id'])
            self.assertEqual(m.read(self.session,[self.session_note['id']])['entries'][0]['body'],'separate kestrel')
            self.assertEqual(m.search(str(self.old),'maple')['entries'],[])
            self.assertEqual(m.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(m.db.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_unmapped_is_quarantined_even_at_same_path(self):
        report=restore(self.snapshot,self.dest)
        archived=next(p for p in report['projects'] if p['source_id']==self.pid)
        self.assertEqual(archived['mode'],'archive')
        with contextlib.closing(Memory(self.dest)) as m:
            self.assertEqual(m.search(str(self.old),'maple')['entries'],[])
            self.assertEqual(m.search_project(archived['destination_id'],'maple')[0]['body'],'private maple')
        p=subprocess.run([sys.executable,'memory.py','--home',str(self.dest),'archive-search',archived['destination_id'],'maple'],capture_output=True,text=True,encoding='utf8',timeout=10)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(json.loads(p.stdout)[0]['body'],'private maple')

    def test_existing_database_is_never_overwritten(self):
        with contextlib.closing(Memory(self.dest)) as m:m.remember(str(self.new),'Existing','must remain')
        with self.assertRaises(ValueError):restore(self.snapshot,self.dest,{self.pid:str(self.new)})
        with contextlib.closing(Memory(self.dest)) as m:
            self.assertEqual(m.search(str(self.new),'remain')['entries'][0]['body'],'must remain')

    def test_failed_mapping_does_not_publish_partial_database(self):
        for mapping in ({'unknown':str(self.new)},{self.pid:str(self.base/'absent')}):
            with self.assertRaises(ValueError):restore(self.snapshot,self.dest,mapping)
            self.assertFalse((self.dest/'memory.sqlite3').exists())
        restore(self.snapshot,self.dest,{self.pid:str(self.new)})

    def test_multiple_sources_to_same_project_refused(self):
        extra=self.base/'extra';extra.mkdir()
        with contextlib.closing(Memory(self.src)) as m:
            second=m.register(str(extra))['id'];m.remember(str(extra),'Other','must not merge')
            snapshot=m.backup()
        with self.assertRaises(ValueError):restore(snapshot,self.dest,{self.pid:str(self.new),second:str(self.new)})
        self.assertFalse((self.dest/'memory.sqlite3').exists())

    def test_session_to_project_implicit_merge_refused(self):
        sid=next(row['id'] for row in inventory(self.snapshot) if row['identity'].startswith('session:'))
        with self.assertRaises(ValueError):restore(self.snapshot,self.dest,{sid:str(self.new)})
        self.assertFalse((self.dest/'memory.sqlite3').exists())

    def test_reexport_of_archive_and_current_project_is_safe(self):
        restore(self.snapshot,self.dest)
        with contextlib.closing(Memory(self.dest)) as m:
            m.remember(str(self.old),'New work','new record')
            snapshot=m.backup()
        target=self.base/'third-machine'
        result=restore(snapshot,target)
        self.assertEqual(result['records'],3)
        ids=[p['destination_id'] for p in result['projects']]
        self.assertEqual(len(ids),len(set(ids)))

    def test_claude_only_install_leaves_codex_absent(self):
        user=self.base/'user'
        setup(self.base/'installed',user,('claude',))
        self.assertTrue((user/'.claude/settings.json').exists())
        self.assertFalse((user/'.codex').exists())
        self.assertTrue((self.base/'installed/app/docs/06-instalace-a-pouziti.md').exists())
        self.assertTrue((self.base/'installed/app/docs/TRANSFER.md').exists())

    def test_codex_only_install_leaves_claude_absent(self):
        user=self.base/'user'
        setup(self.base/'installed',user,('codex',))
        self.assertTrue((user/'.codex/hooks.json').exists())
        self.assertFalse((user/'.claude').exists())
        self.assertFalse((user/'.claude.json').exists())

    def test_reinstall_preserves_unrelated_hook_in_same_group(self):
        user=self.base/'user';home=self.base/'installed'
        setup(home,user,('claude',))
        path=user/'.claude/settings.json'
        doc=json.loads(path.read_text(encoding='utf8'))
        other={'type':'command','command':'unrelated-command'}
        doc['hooks']['Stop'][0]['hooks'].append(other)
        path.write_text(json.dumps(doc),encoding='utf8')
        setup(home,user,('claude',))
        doc=json.loads(path.read_text(encoding='utf8'))
        commands=[h for g in doc['hooks']['Stop'] for h in g['hooks']]
        self.assertIn(other,commands)
        self.assertEqual(len(commands),2)

    def test_unknown_host_refused_before_creating_files(self):
        target=self.base/'installed'
        with self.assertRaises(ValueError):setup(target,self.base/'user',('unknown',))
        self.assertFalse(target.exists())

    def test_powershell_launcher_in_isolated_profile(self):
        user=self.base/'launcher user';user.mkdir()
        environment={**os.environ,'USERPROFILE':str(user)}
        p=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-File',
                          str(Path(__file__).with_name('install.ps1')),'-HostApp','claude'],
                         env=environment,capture_output=True,text=True,timeout=30)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertTrue((user/'.claude/settings.json').exists())
        self.assertFalse((user/'.codex').exists())
        with contextlib.closing(Memory(user/'.project-memory')) as m:
            self.assertEqual(m.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')

if __name__=='__main__':unittest.main(verbosity=2)
