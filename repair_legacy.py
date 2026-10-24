"""Restore full legacy content in resumable batches without changing existing scopes."""
import argparse
import contextlib
import datetime as dt
import json
from pathlib import Path
import sqlite3
import uuid
from memory import Memory, digest, now, safe_text, write_json_atomic
from import_legacy import TABLES, render, restore_existing


def repair(source,home,mapping=None,batch_size=100):
    source=Path(source).resolve(strict=True);home=Path(home).resolve()
    if not (home/'memory.sqlite3').exists():raise ValueError('Repair requires an existing memory database.')
    origin='claude-mem:'+digest(str(source).casefold())[:20]
    folder=home/'backups';folder.mkdir(exist_ok=True)
    stamp=dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    snapshot=folder/('legacy-full-source-'+stamp+'.sqlite3')
    # Preserve a consistent source including WAL; source database is read-only.
    with contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src, contextlib.closing(sqlite3.connect(snapshot)) as dest:
        src.backup(dest)
    with contextlib.closing(Memory(home,timeout=30)) as mem, contextlib.closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro',uri=True)) as src:
        src.row_factory=sqlite3.Row
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid source snapshot.')
        backup=mem.backup()
        report={'started':now(),'complete':False,'source':str(source),'source_snapshot':str(snapshot),
                'backup':backup,'origin':origin,'counts':{},'verified':{},'expanded':0,'inserted':0,
                'existing_assignments_preserved':True,'source_rows_exact':True}
        output=home/'full-content-report.json'
        write_json_atomic(output,report)
        sessions={r['id']:dict(r) for r in src.execute('SELECT * FROM sdk_sessions')}
        for table in TABLES:
            cursor=src.execute('SELECT * FROM '+table+' ORDER BY id');count=0
            report['counts'][table]=0
            while batch:=cursor.fetchmany(batch_size):
                with mem.transaction():
                    for raw in batch:
                        data=dict(raw);key=table+':'+str(data['id'])
                        entry=mem.db.execute('SELECT * FROM entries WHERE source=? AND source_key=?',(origin,key)).fetchone()
                        if entry:
                            identity=(entry['id'],entry['project_id'],entry['session_id'],entry['source_hash'])
                            expanded=bool(entry['truncated'])
                            restored=restore_existing(mem,entry,data,table)
                            assert identity==tuple(restored[k] for k in ('id','project_id','session_id','source_hash'))
                            report['expanded']+=expanded
                        else:
                            label=data.get('project') or sessions.get(data.get('session_db_id'),{}).get('project') or '(unknown)'
                            project=mem.register(mapping[label]) if label in (mapping or {}) else mem.legacy(label)
                            kind,title,body=render(data,table)
                            entry=mem.insert(project['id'],kind,title,body,origin,key,created=data.get('created_at') or now(),
                                session=data.get('content_session_id') or data.get('memory_session_id'),cwd=data.get('cwd'),
                                source_hash=digest(json.dumps(data,sort_keys=True,ensure_ascii=False)))
                            mem.store_original(entry['id'],data);report['inserted']+=1
                        count+=1
                report['counts'][table]=count;write_json_atomic(output,report)
            # Verify actual complete stored bytes, not only the saved source fingerprint.
            verified=0
            for raw in src.execute('SELECT * FROM '+table+' ORDER BY id'):
                data=dict(raw)
                entry=mem.db.execute('SELECT * FROM entries WHERE source=? AND source_key=?',(origin,table+':'+str(data['id']))).fetchone()
                if not entry or entry['truncated'] or entry['body']!=safe_text(render(data,table)[2]):
                    raise ValueError('Complete stored body mismatch.')
                if mem.original(entry['id'])!=json.dumps(data,sort_keys=True,ensure_ascii=False):
                    raise ValueError('Complete original row mismatch.')
                verified+=1
            report['verified'][table]=verified;write_json_atomic(output,report)
        assert report['counts']==report['verified']
        if mem.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or mem.db.execute('PRAGMA foreign_key_check').fetchone():
            raise ValueError('Destination integrity check failed.')
        mem.db.execute("INSERT INTO entries_fts(entries_fts,rank) VALUES('integrity-check',1)")
        report.update(complete=True,finished=now(),integrity='ok',fts_integrity='ok')
        write_json_atomic(output,report)
        return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--home',required=True)
    p.add_argument('--map',action='append',default=[],help='Only for new, previously unimported rows: LABEL=ABSOLUTE_FOLDER')
    a=p.parse_args();print(json.dumps(repair(a.source,a.home,dict(x.split('=',1) for x in a.map)),ensure_ascii=False,indent=2))
