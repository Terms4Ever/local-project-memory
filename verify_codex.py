"""Host discovery without model calls; trust only this installation's reviewed hooks."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
import tomllib
from memory import write_json_atomic

def inspect():
    q=queue.Queue()
    p=subprocess.Popen(['codex','app-server','--stdio'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                       encoding='utf8',text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def reader():
        for line in p.stdout:
            try:q.put(json.loads(line))
            except ValueError:pass
    threading.Thread(target=reader,daemon=True).start()
    def call(i,method,params):
        p.stdin.write(json.dumps({'id':i,'method':method,'params':params})+'\n');p.stdin.flush()
        while True:
            result=q.get(timeout=45)
            if result.get('id')==i:return result
    try:
        call(1,'initialize',{'clientInfo':{'name':'project-memory-verification','version':'1'},'capabilities':{'experimentalApi':True}})
        p.stdin.write('{"method":"initialized"}\n');p.stdin.flush()
        hooks=call(2,'hooks/list',{'cwds':[str(Path.cwd())]})
        mcp=call(3,'mcpServerStatus/list',{'serverName':'project-memory'})
        return hooks,mcp
    finally:
        p.terminate();p.wait(timeout=10)

def owned(command,script):
    if script in command:return True
    marker='-EncodedCommand '
    if marker in command:
        try:return script in base64.b64decode(command.split(marker,1)[1].strip()).decode('utf-16le')
        except (ValueError,UnicodeError):pass
    return False

def verify(trust=False,manifest=None):
    home=Path.home()/'.project-memory';script=str(home/'app/memory.py')
    hooks,mcp=inspect()
    if 'error' in hooks:raise RuntimeError(str(hooks['error']))
    selected=[];errors=[];warnings=[]
    for entry in hooks.get('result',{}).get('data',[]):
        errors.extend(entry.get('errors',[]));warnings.extend(entry.get('warnings',[]))
        selected.extend(h for h in entry['hooks'] if owned(h.get('command',''),script))
    if trust:
        if errors or len(selected)!=5:raise ValueError('Unexpected hook discovery; refusing trust changes.')
        path=Path.home()/'.codex/config.toml';before=path.read_text(encoding='utf8');text=before
        for h in selected:
            header='[hooks.state.'+json.dumps(h['key'])+']'
            block=header+'\ntrusted_hash = '+json.dumps(h['currentHash'])+'\n'
            pattern=r'(?m)^'+re.escape(header)+r'\n[^\[]*'
            text=re.sub(pattern,lambda _:block+'\n',text) if re.search(pattern,text) else text+'\n'+block
        tomllib.loads(text)
        if path.read_text(encoding='utf8')!=before:raise RuntimeError('Concurrent config edit')
        # Keep an immediate recovery copy; original installation manifest remains authoritative.
        (home/'config-backups/config-before-memory-hook-trust.toml').write_text(before,encoding='utf8')
        path.write_text(text,encoding='utf8')
        if manifest:
            data=json.loads(Path(manifest).read_text(encoding='utf8'))
            for item in data['files']:
                if Path(item['path'])==path:item['installed_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            write_json_atomic(Path(manifest),data)
        return verify(False)
    result={'hooks':[{'event':h['eventName'],'trusted':h['trustStatus'],'enabled':h['enabled']} for h in selected],
            'errors':errors,'warnings':warnings,'mcp':mcp}
    write_json_atomic(home/'codex-verification.json',result)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--trust-reviewed-hooks',action='store_true');p.add_argument('--manifest')
    a=p.parse_args();print(json.dumps(verify(a.trust_reviewed_hooks,a.manifest),ensure_ascii=False,indent=2))
