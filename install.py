"""Additive local installation. Preserves existing host configuration and old plugin."""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tomllib
import uuid
from memory import Memory, VERSION, write_json_atomic

EVENTS=('SessionStart','UserPromptSubmit','PostToolUse','Stop','SubagentStop')

def setup(home=None,user=None,hosts=('claude','codex')):
    hosts=tuple(hosts)
    if not hosts or any(host not in ('claude','codex') for host in hosts):
        raise ValueError('Choose claude, codex, or both.')
    if os.name!='nt':raise ValueError('The installer currently supports Windows only.')
    user=Path(user or Path.home());home=Path(home or user/'.project-memory').resolve()
    app=home/'app';app.mkdir(parents=True,exist_ok=True)
    source=Path(__file__).resolve().parent
    for name in ('memory.py','import_legacy.py','install.py','README.md','verify_codex.py','verify_session.py','transfer.py'):
        p=source/name
        if p.exists() and p.resolve()!=(app/name).resolve():shutil.copy2(p,app/name)
    # README links stay usable in the installed copy; never copy runtime data.
    for p in (source/'docs').glob('*.md'):
        dest=app/'docs'/p.name
        if p.resolve()!=dest.resolve():
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(p,dest)
    mem=Memory(home);mem.close()
    records=[];plans=[];originals={}
    batch=home/'config-backups'/(dt.datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6])
    batch.mkdir(parents=True,exist_ok=True)
    def read_text(path):
        raw=path.read_bytes() if path.exists() else None
        originals[str(path)]=raw
        return raw.decode('utf-8-sig') if raw is not None else ''
    def read_json(path):
        return json.loads(read_text(path) or '{}')
    def change(path,value):
        previous=originals[str(path)]
        raw=value.encode('utf8')
        if previous==raw:return
        plans.append((path,previous,raw))
    python=str(Path(sys.executable).resolve());script=str(app/'memory.py')
    def command(platform,event):
        # Encoded PowerShell avoids differences in quote parsing between host shells.
        args=[python,script,'--home',str(home),'hook',platform,event]
        expr='& '+' '.join("'"+a.replace("'","''")+"'" for a in args)+'; exit $LASTEXITCODE'
        return 'powershell.exe -NoProfile -NonInteractive -EncodedCommand '+base64.b64encode(expr.encode('utf-16le')).decode('ascii')
    def add_hooks(doc,platform):
        hooks=doc.setdefault('hooks',{})
        for event in EVENTS+(('PostToolUseFailure',) if platform=='claude' else ()):
            groups=hooks.setdefault(event,[])
            # Own groups only; leave every pre-existing rule and notification unchanged.
            own_commands={command(platform,e) for e in EVENTS+('PostToolUseFailure',)}
            preserved=[]
            for group in groups:
                remaining=[h for h in group.get('hooks',[]) if not (h.get('command','') in own_commands or script in h.get('command',''))]
                if remaining:preserved.append({**group,'hooks':remaining})
            groups[:]=preserved
            h={'type':'command','command':command(platform,event),'timeout':20}
            groups.append({'hooks':[h],**({'matcher':'.*'} if event in ('PostToolUse','PostToolUseFailure') else {})})
        return doc
    server={'type':'stdio','command':python,'args':[script,'--home',str(home),'serve']}
    if 'claude' in hosts:
        path=user/'.claude/settings.json'
        doc=read_json(path)
        change(path,json.dumps(add_hooks(doc,'claude'),ensure_ascii=False,indent=2)+'\n')
        path=user/'.claude.json'
        doc=read_json(path)
        previous_server=doc.setdefault('mcpServers',{}).get('project-memory')
        if previous_server and previous_server!=server:raise ValueError('Existing project-memory MCP differs; refusing overwrite.')
        doc['mcpServers']['project-memory']=server
        change(path,json.dumps(doc,ensure_ascii=False,indent=2)+'\n')
    if 'codex' in hosts:
        path=user/'.codex/hooks.json'
        doc=read_json(path)
        change(path,json.dumps(add_hooks(doc,'codex'),ensure_ascii=False,indent=2)+'\n')
        path=user/'.codex/config.toml'
        text=read_text(path)
        cfg=tomllib.loads(text)
        if 'project-memory' not in cfg.get('mcp_servers',{}):
            text+='\n[mcp_servers.project-memory]\ncommand = '+json.dumps(python)+'\nargs = '+json.dumps([script,'--home',str(home),'serve'])+'\nstartup_timeout_sec = 20\ntool_timeout_sec = 30\n'
        else:
            old=cfg['mcp_servers']['project-memory']
            if old.get('command')!=python or old.get('args')!=server['args']:raise ValueError('Existing Codex MCP differs; refusing overwrite.')
        tomllib.loads(text);change(path,text)
    report={'version':VERSION,'home':str(home),'hosts':list(hosts),'files':records,'old_plugin':'unchanged; parallel validation mode',
            'activation':'New host sessions; Codex hook trust must be reviewed separately.'}
    # Validate all preconditions before changing any host configuration.
    for path,previous,raw in plans:
        if (path.read_bytes() if path.exists() else None)!=previous:raise RuntimeError('Concurrent config edit: '+str(path))
    for path,previous,raw in plans:
        path.parent.mkdir(parents=True,exist_ok=True)
        if (path.read_bytes() if path.exists() else None)!=previous:raise RuntimeError('Concurrent config edit; see rollback manifest: '+str(path))
        dest=batch/(str(len(records))+'-'+path.name)
        if previous is not None:dest.write_bytes(previous)
        records.append({'path':str(path),'backup':str(dest) if previous is not None else None,
                        'installed_sha256':hashlib.sha256(raw).hexdigest()})
        write_json_atomic(batch/'manifest.json',report)
        tmp=path.with_name(path.name+'.memory-'+uuid.uuid4().hex+'.tmp')
        with open(tmp,'xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        os.replace(tmp,path)
    write_json_atomic(batch/'manifest.json',report)
    return report

def rollback(manifest):
    data=json.loads(Path(manifest).read_text(encoding='utf8'))
    # Refuse to overwrite any later user/app edits. No blind full-file restoration.
    for item in data['files']:
        path=Path(item['path'])
        if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest()!=item['installed_sha256']:
            raise ValueError('Config changed since install; selective rollback needed: '+str(path))
    for item in data['files']:
        path=Path(item['path'])
        if item['backup']:shutil.copy2(item['backup'],path)
        else:path.unlink()
    return {'restored':len(data['files']),'database':'preserved'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--home');p.add_argument('--user');p.add_argument('--rollback')
    p.add_argument('--host',choices=['claude','codex','both'],default='both')
    a=p.parse_args();result=rollback(a.rollback) if a.rollback else setup(a.home,a.user,('claude','codex') if a.host=='both' else (a.host,))
    print(json.dumps(result,ensure_ascii=False,indent=2))
