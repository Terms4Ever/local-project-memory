"""Inspect or restore a private memory snapshot onto a new PC. Never merge live databases."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import sqlite3
import uuid
from memory import Memory

def inventory(snapshot):
    source=Path(snapshot).resolve(strict=True)
    with contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        return [dict(row) for row in db.execute('''SELECT p.id,p.name,p.root,p.identity,
            count(e.id) AS entries FROM projects p LEFT JOIN entries e ON e.project_id=p.id
            GROUP BY p.id ORDER BY p.name''')]

def restore(snapshot,home,mapping=None):
    source=Path(snapshot).resolve(strict=True)
    home=Path(home).expanduser().resolve()
    target=home/'memory.sqlite3'
    if target.exists() or any((home/folder).exists() for folder in ('pending','failed')):
        raise ValueError('Restore requires a fresh memory home without a database or journals. Existing data is never overwritten.')
    home.mkdir(parents=True,exist_ok=True)
    temp=home/('restore-'+uuid.uuid4().hex+'.sqlite3')
    mapping=mapping or {}
    try:
        with contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src:
            with contextlib.closing(sqlite3.connect(temp)) as dst:src.backup(dst)
        # Use a separate staging directory so Memory can validate/migrate normally.
        staging=home/('restore-stage-'+uuid.uuid4().hex)
        staging.mkdir()
        staged=staging/'memory.sqlite3'
        os.replace(temp,staged)
        try:
            with contextlib.closing(Memory(staging)) as mem:
                if mem.db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    raise ValueError('Snapshot failed integrity check.')
                projects=[dict(row) for row in mem.db.execute('SELECT * FROM projects')]
                by_id={p['id']:p for p in projects}
                if set(mapping)-set(by_id):raise ValueError('Mapping contains an unknown source project ID.')
                if any(by_id[pid]['identity'].startswith('session:') for pid in mapping):
                    raise ValueError('Session history is not automatically merged into a project.')
                count=mem.db.execute('SELECT count(*) FROM entries').fetchone()[0]
                result=[];destinations=set();archive_batch=uuid.uuid4().hex
                with mem.transaction():
                    # Old machine aliases must not accidentally resolve on this machine.
                    mem.db.execute('DELETE FROM aliases')
                    for old in projects:
                        if old['identity'].startswith('session:'):
                            result.append({'source_id':old['id'],'destination_id':old['id'],'mode':'session preserved'})
                            continue
                        archive=mem._project('archive:transfer:'+archive_batch+':'+old['identity'],old['name'],legacy=True)
                        mem.db.execute('UPDATE entries SET project_id=? WHERE project_id=?',(archive['id'],old['id']))
                        mem.db.execute('DELETE FROM projects WHERE id=?',(old['id'],))
                        result.append({'source_id':old['id'],'destination_id':archive['id'],'mode':'archive'})
                    for item in result:
                        if item['source_id'] not in mapping:continue
                        dest=mem.register(mapping[item['source_id']])
                        if dest['id'] in destinations:raise ValueError('Multiple source projects map to one destination; refusing an implicit merge.')
                        destinations.add(dest['id'])
                        old_id=item['destination_id']
                        mem.db.execute('UPDATE entries SET project_id=? WHERE project_id=?',(dest['id'],old_id))
                        mem.db.execute('DELETE FROM projects WHERE id=?',(old_id,))
                        item.update(destination_id=dest['id'],mode='mapped project',root=dest['root'])
                    if mem.db.execute('SELECT count(*) FROM entries').fetchone()[0]!=count:
                        raise ValueError('Record count changed during restore.')
                    if mem.db.execute('PRAGMA foreign_key_check').fetchall():
                        raise ValueError('Restored data failed relationship checks.')
                mem.db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            # Atomic publish with no overwrite, even if another process created a DB.
            os.link(staged,target)
            return {'database':str(target),'records':count,'projects':result,
                    'note':'No host configs or credentials copied. Unmapped projects remain archives; session IDs preserved.'}
        finally:
            # Delete only files created by this invocation inside its unique staging dir.
            for path in staging.iterdir():path.unlink()
            staging.rmdir()
    finally:
        temp.unlink(missing_ok=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='cmd',required=True)
    p=sub.add_parser('list');p.add_argument('snapshot')
    p=sub.add_parser('restore');p.add_argument('snapshot')
    p.add_argument('--home',default=str(Path.home()/'.project-memory'))
    p.add_argument('--map',action='append',default=[],help='SOURCE_PROJECT_ID=NEW_ABSOLUTE_FOLDER')
    args=parser.parse_args()
    if args.cmd=='list':result=inventory(args.snapshot)
    else:
        pairs=[item.split('=',1) for item in args.map]
        if any(len(pair)!=2 for pair in pairs):parser.error('--map requires ID=PATH')
        mapping=dict(pairs)
        if len(mapping)!=len(pairs):parser.error('Duplicate source project ID')
        result=restore(args.snapshot,args.home,mapping)
    print(json.dumps(result,ensure_ascii=False,indent=2))
