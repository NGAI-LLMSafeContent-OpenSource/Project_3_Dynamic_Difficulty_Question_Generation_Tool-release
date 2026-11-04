#!/usr/bin/env python3
"""Run declared clean-environment CPU tests and real local HTTP smoke checks."""
from __future__ import annotations
import json,os,signal,socket,subprocess,sys,tempfile,time,urllib.request,urllib.error,venv
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=json.loads((ROOT/'tools/release_smoke.json').read_text(encoding='utf-8'))
def run(argv,cwd,env):
 print('RUN',json.dumps(argv,ensure_ascii=False),flush=True)
 subprocess.run(argv,cwd=cwd,env=env,check=True,timeout=SPEC.get('command_timeout',300))
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def request(url,check):
 data=None if 'body' not in check else json.dumps(check['body'],ensure_ascii=False).encode()
 req=urllib.request.Request(url,data=data,method=check.get('method','GET'),headers={'Content-Type':'application/json'})
 try:
  with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=5) as response:status=response.status;body=response.read()
 except urllib.error.HTTPError as exc:status=exc.code;body=exc.read()
 assert status==check.get('status',200),(url,status,body[:100])
 if check.get('text_contains'):assert check['text_contains'].encode() in body,url
 if check.get('json_contains'):
  obj=json.loads(body)
  for key,value in check['json_contains'].items():assert obj.get(key)==value,(url,key)
 return {'path':check['path'],'status':status}
with tempfile.TemporaryDirectory(prefix='release-runtime-') as directory:
 temp=Path(directory);python=sys.executable;env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ['TOKEN','SECRET','PASSWORD','API_KEY']) and not k.startswith('GIT_') and k not in ['PYTHONPATH','PYTHONHOME']}
 env.update(NO_PROXY='127.0.0.1,localhost,::1',no_proxy='127.0.0.1,localhost,::1',PYTHONDONTWRITEBYTECODE='1')
 if SPEC.get('requirements'):
  venv.EnvBuilder(with_pip=False,system_site_packages=False).create(temp/'venv');python=str(temp/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python'))
  run([sys.executable,'-m','pip','--isolated','--python',python,'install','--no-cache-dir','-r',str(ROOT/SPEC['requirements'])],ROOT,env)
 def expand(argv,number=None):return [str(a).replace('{python}',python).replace('{root}',str(ROOT)).replace('{temp}',str(temp)).replace('{port}',str(number or '')) for a in argv]
 results=[]
 for item in SPEC.get('commands',[]):run(expand(item['argv']),ROOT/item.get('cwd','.'),env)
 for item in SPEC.get('servers',[]):
  number=port();log=temp/('server-'+str(number)+'.log');server_env=dict(env)
  server_env.update({k:str(v).replace('{temp}',str(temp)).replace('{port}',str(number)) for k,v in item.get('env',{}).items()})
  with log.open('wb') as output:
   process=subprocess.Popen(expand(item['argv'],number),cwd=ROOT/item.get('cwd','.'),env=server_env,stdout=output,stderr=output,start_new_session=os.name!='nt')
   try:
    deadline=time.monotonic()+45;ready={'path':item.get('ready','/'),'status':200}
    while True:
     try:request('http://127.0.0.1:'+str(number)+ready['path'],ready);break
     except Exception:
      if process.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Server failed: '+log.read_text(errors='replace')[-2000:])
      time.sleep(.15)
    for check in item['checks']:results.append(request('http://127.0.0.1:'+str(number)+check['path'],check))
   finally:
    if process.poll() is None:
     if os.name!='nt':os.killpg(process.pid,signal.SIGTERM)
     else:process.terminate()
     try:process.wait(timeout=10)
     except subprocess.TimeoutExpired:process.kill();process.wait()
 print(json.dumps({'passed':True,'scope':SPEC['scope'],'http_checks':results,'command_groups':len(SPEC.get('commands',[]))},ensure_ascii=False))
