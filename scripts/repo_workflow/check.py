"""Controller verification: separate offline build and read-only trusted test container."""
import argparse,hashlib,json,subprocess,time,uuid,xml.etree.ElementTree as ET
from pathlib import Path
IMAGE='hermes-repo-workflow:v2'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def identity(image):return subprocess.check_output(['docker','image','inspect','--format','{{.Id}}',image],text=True).strip()
def stopped(name):
    subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=20)
    p=subprocess.run(['docker','container','inspect',name],capture_output=True,text=True,timeout=10)
    if p.returncode==0 or 'No such container' not in p.stderr and 'No such object' not in p.stderr:raise RuntimeError('container cleanup unconfirmed: '+name)

def isolated(image,mounts,args,output,label):
    name='hermes-repo-check-'+uuid.uuid4().hex
    cmd=['docker','run','--name',name,'--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','2g','--cpus','2','--tmpfs','/tmp:rw,exec,nosuid,nodev,size=512m']
    for src,dst,mode in mounts:cmd+=['-v',f'{src.resolve()}:{dst}:{mode}']
    cmd+=['-w','/tmp',image,*args]
    try:
        p=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
        (output/(label+'-stdout.txt')).write_text(p.stdout);(output/(label+'-stderr.txt')).write_text(p.stderr)
        return p.returncode,cmd
    finally:stopped(name)

def check(candidate,trusted,output,selector,image=IMAGE,test_file='test_cli_convert.py'):
    if Path(test_file).name!=test_file or not test_file.endswith('.py'):raise ValueError('invalid trusted test filename')
    output.mkdir(parents=True,exist_ok=False);started=time.monotonic();result={'selector':selector,'test_file':test_file,'image':image,'image_id':identity(image),'valid':False,'passed':False,'cases':[],'identity':None}
    try:
        build=output/'build';build.mkdir()
        rc,cmd=isolated(image,[(candidate,'/input','ro'),(build,'/build-out','rw')],['sh','-c','cp -R /input /tmp/candidate && python -I -m pip install --no-index --no-deps --no-build-isolation --no-compile -e /tmp/candidate --prefix /tmp/install && cp /tmp/install/bin/sqlite-utils /build-out/cli-entrypoint'],output,'build')
        result.update(build_returncode=rc,build_command=cmd)
        if rc:raise RuntimeError('isolated candidate installation failed')
        if 'sqlite_utils.cli import cli' not in (build/'cli-entrypoint').read_text():raise RuntimeError('unexpected installed CLI entrypoint')
        harness=Path(__file__).with_name('trusted_harness.py')
        rc,cmd=isolated(image,[(candidate,'/input','ro'),(harness,'/harness.py','ro'),(build/'cli-entrypoint','/entrypoint','ro')],['python','-I','/harness.py','cli','--help'],output,'cli')
        result['cli_returncode']=rc
        if rc or 'Usage:' not in (output/'cli-stdout.txt').read_text():raise RuntimeError('installed CLI canary failed')
        mounts=[(candidate,'/input','ro'),(trusted,'/trusted','ro'),(harness,'/harness.py','ro'),(output,'/out','rw')]
        rc,cmd=isolated(image,mounts,['python','-I','/harness.py','collect',test_file,selector],output,'collect');result['collection_returncode']=rc
        if rc:raise RuntimeError('trusted collection failed')
        expected=json.loads((output/'collected.json').read_text())
        rc,cmd=isolated(image,mounts,['python','-I','/harness.py','run',test_file,selector],output,'test');result.update(returncode=rc,test_command=cmd)
        if (output/'junit.xml').exists():
            for c in ET.parse(output/'junit.xml').iter('testcase'):
                result['cases'].append({'id':c.attrib['classname']+'::'+c.attrib['name'],'outcome':'error' if c.find('error') is not None else 'failed' if c.find('failure') is not None else 'skipped' if c.find('skipped') is not None else 'passed'})
        result['identity']=json.loads((output/'identity.json').read_text())
        actual=sorted(c['id'] for c in result['cases'])
        result['valid']=bool(expected) and actual==sorted(expected) and all(c['outcome'] not in ('error','skipped') for c in result['cases'])
        result['passed']=result['valid'] and rc==0 and all(c['outcome']=='passed' for c in result['cases'])
    except Exception as exc:result['error']=str(exc)
    result['seconds']=time.monotonic()-started
    result['evidence_sha256']={f.name:sha(f) for f in output.iterdir() if f.is_file()}
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--candidate',type=Path,required=True);p.add_argument('--trusted',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--selector',required=True);p.add_argument('--test-file',default='test_cli_convert.py');a=p.parse_args()
    r=check(a.candidate,a.trusted,a.output,a.selector,test_file=a.test_file);print(json.dumps(r,indent=2));raise SystemExit(0 if r['valid'] else 2)
