"""Read-only claude-mem migration through a consistent SQLite backup."""
import argparse
import contextlib
import datetime as dt
import json
from pathlib import Path
import sqlite3
import uuid
from memory import Memory, digest, now, safe_text, secret_file_event, write_json_atomic

TABLES=('observations','session_summaries','user_prompts','tool_uses')

def render(data,table):
    if table=='observations':
        return ('legacy_observation',data.get('title') or 'Historical observation',
                {k:data.get(k) for k in ('text','subtitle','facts','narrative','concepts','files_read','files_modified') if data.get(k)})
    if table=='session_summaries':
        return ('legacy_summary',(data.get('request') or 'Historical session summary')[:200],
                {k:data.get(k) for k in ('request','investigated','learned','completed','next_steps','notes','files_read','files_edited') if data.get(k)})
    if table=='user_prompts':return ('prompt','Historical user prompt',data.get('prompt_text') or '')
    if table!='tool_uses':raise ValueError('Unknown legacy table.')
    try:inp=json.loads(data.get('tool_input') or '{}')
    except (TypeError,ValueError):inp=data.get('tool_input') or ''
    body=({'omitted':'Credential file content omitted from searchable copy.'} if secret_file_event({'tool_input':inp})
          else {k:data.get(k) for k in ('tool_name','tool_input','tool_response') if data.get(k)})
    return ('legacy_tool','Historical tool: '+str(data.get('tool_name')),body)

def restore_existing(mem,entry,data,table):
    """Repair content only. Never recompute an already assigned project or session."""
    original_hash=digest(json.dumps(data,sort_keys=True,ensure_ascii=False))
    if entry['source_hash']!=original_hash:raise ValueError('Source row changed: '+table+':'+str(data['id']))
    body=safe_text(render(data,table)[2])
    if entry['body']!=body and not (entry['truncated'] and body.startswith(entry['body'])):
        raise ValueError('Existing content is not the expected source prefix; refusing overwrite.')
    mem.store_original(entry['id'],data)
    if entry['body']!=body or entry['truncated']:
        mem.db.execute('UPDATE entries SET body=?,truncated=0 WHERE id=?',(body,entry['id']))
    return dict(mem.db.execute('SELECT * FROM entries WHERE id=?',(entry['id'],)).fetchone())

def migrate(source,home,mapping=None):
    source=Path(source).resolve(strict=True)
    home=Path(home).resolve();backup_dir=home/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
    snapshot=backup_dir/('claude-mem-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]+'.sqlite3')
    with contextlib.closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as original:
        with contextlib.closing(sqlite3.connect(snapshot)) as dest:original.backup(dest)
    origin='claude-mem:'+digest(str(source).casefold())[:20]
    with contextlib.closing(sqlite3.connect(snapshot.as_uri()+'?mode=ro',uri=True)) as src, contextlib.closing(Memory(home)) as mem:
        src.row_factory=sqlite3.Row
        if src.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Source backup failed integrity check.')
        sessions={row['id']:dict(row) for row in src.execute('SELECT * FROM sdk_sessions')}
        projects={}
        labels={row[0] for row in src.execute('SELECT DISTINCT project FROM sdk_sessions')}
        for table in ('observations','session_summaries','tool_uses'):
            labels.update(row[0] for row in src.execute('SELECT DISTINCT project FROM '+table))
        for label in labels:
            projects[label]=mem.register(mapping[label]) if label in (mapping or {}) else mem.legacy(label or '(unknown)')
        counts={};verified={};truncated={}
        with mem.transaction():
            for table in TABLES:
                counts[table]=0;truncated[table]=0
                for row in src.execute('SELECT * FROM '+table+' ORDER BY id'):
                    data=dict(row)
                    session=sessions.get(data.get('session_db_id'),{})
                    label=data.get('project') or session.get('project') or '(unknown)'
                    if label not in projects:projects[label]=mem.legacy(label)
                    kind,title,body=render(data,table)
                    original_hash=digest(json.dumps(data,sort_keys=True,ensure_ascii=False))
                    existing=mem.db.execute('SELECT * FROM entries WHERE source=? AND source_key=?',(origin,table+':'+str(data['id']))).fetchone()
                    if existing:
                        entry=restore_existing(mem,existing,data,table)
                    else:
                        entry=mem.insert(projects[label]['id'],kind,title,body,origin,table+':'+str(data['id']),
                                         created=data.get('created_at') or now(),session=data.get('content_session_id') or data.get('memory_session_id'),
                                         cwd=data.get('cwd'),source_hash=original_hash)
                        mem.store_original(entry['id'],data)
                    counts[table]+=1;truncated[table]+=entry['truncated']
                verified[table]=mem.db.execute('SELECT count(*) FROM entries WHERE source=? AND source_key LIKE ?',
                                               (origin,table+':%')).fetchone()[0]
                if counts[table]!=verified[table]:raise ValueError('Source/destination count mismatch: '+table)
            manifest={'source':str(source),'source_snapshot':str(snapshot),'origin':origin,
                      'counts':counts,'verified':verified,'bounded_search_copies':truncated,
                      'projects':{k:{'id':v['id'],'root':v['root'],'legacy':bool(v['legacy'])} for k,v in projects.items()},
                      'sessions_preserved_in_snapshot':len(sessions),'finished':now(),
                      'note':'Complete source rows retained in entry_originals and verified by SHA-256. Search excerpts and MCP pages are bounded, stored bodies are not. Credential filtering remains on model-facing content. Existing project assignments preserved.'}
            mem.db.execute('INSERT INTO imports VALUES(?,?,?) ON CONFLICT(source) DO UPDATE SET manifest=excluded.manifest,finished_at=excluded.finished_at',
                           (origin,json.dumps(manifest,ensure_ascii=False),now()))
        write_json_atomic(home/'migration-report.json',manifest)
        return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--home',required=True)
    p.add_argument('--map',action='append',default=[],help='Explicit historical name=absolute project directory')
    a=p.parse_args();mapping=dict(v.split('=',1) for v in a.map)
    print(json.dumps(migrate(a.source,a.home,mapping),ensure_ascii=False,indent=2))
