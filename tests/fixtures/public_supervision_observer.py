"""只在真实原生stdout与公开监督器之间注入回复故障；不改安装器、锁或二进制。"""
import importlib.util,json,os,runpy,subprocess,sys,threading
from pathlib import Path
script,logfile,fault,sequence,*argv=sys.argv[1:];sequence=int(sequence);original_spec=importlib.util.spec_from_file_location;original_popen=subprocess.Popen;log=Path(logfile);guard=threading.Lock()
def record(row):
 with guard,log.open('a') as stream:stream.write(json.dumps(row)+'\n')
class Input:
 def __init__(self,stream):self.stream=stream
 @property
 def closed(self):return self.stream.closed
 def write(self,data):
  result=self.stream.write(data);record({'confirmation':data.decode()});return result
 def flush(self):return self.stream.flush()
 def close(self):return self.stream.close()
class Process:
 def __init__(self,args,**kwargs):
  self.child=original_popen(args,**kwargs);record({'launch':args});self.stdin=Input(self.child.stdin);read,write=os.pipe();self.stdout=os.fdopen(read,'rb',buffering=0)
  def forward():
   with os.fdopen(write,'wb',buffering=0) as output:
    try:
     for line in self.child.stdout:
      event=json.loads(line);record({'nativeEvent':event})
      if event['sequence']==sequence:
       if fault=='duplicate':line=line.rstrip()[:-1]+b',"sequence":'+str(sequence).encode()+b'}\n'
       elif fault=='nonfinite':event['result']={'value':float('inf')};line=(json.dumps(event)+'\n').encode()
       elif fault=='semantic':event['result']={'error':'test-only reply semantic failure'};line=(json.dumps(event)+'\n').encode()
       elif fault=='wrong-request':event['arguments']={'id':'layer.new.layer','params':{'name':'Other'}};line=(json.dumps(event)+'\n').encode()
       elif fault=='save-array':event['result']=[];line=(json.dumps(event)+'\n').encode()
       elif fault=='wrong-save-path':event['result']['path']+='.wrong';line=(json.dumps(event)+'\n').encode()
       elif fault=='extra-frame':line+=b'{}\n'
      output.write(line)
    except (BrokenPipeError,OSError):pass
    finally:self.child.stdout.close()
  threading.Thread(target=forward,daemon=True).start()
 def __getattr__(self,name):return getattr(self.child,name)
def popen(args,*rest,**kwargs):
 if len(args)>2 and args[1] in {'run','batch','convert','droplet'} and '--supervised' in args:
  assert not rest;return Process(args,**kwargs)
 return original_popen(args,*rest,**kwargs)
def observe(name,location,*args,**kwargs):
 spec=original_spec(name,location,*args,**kwargs)
 if Path(location).name=='cli_supervisor.py':
  execute=spec.loader.exec_module
  def hooked(module):execute(module);module.subprocess.Popen=popen
  spec.loader.exec_module=hooked
 return spec
importlib.util.spec_from_file_location=observe;sys.argv=[script,*argv];runpy.run_path(script,run_name='__main__')
