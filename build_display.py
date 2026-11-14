from pathlib import Path
import subprocess,json,hashlib,os,shutil
from config import load
D=Path(__file__).resolve().parent
def main():
    out=D/'build';inc=D/'native/include';link=out/'link';logs=[]
    cfg=load();clang=shutil.which(cfg['clang']) or cfg['clang'];ld=shutil.which(cfg['linker']) or cfg['linker']
    (D/'reports').mkdir(exist_ok=True)
    for n in ['gralloc-bench','egl-probe','seed-rng']:
        obj=out/(n+'.o');target=out/('gralloc.bench.so' if n=='gralloc-bench' else n)
        commands=[[clang,'--target=aarch64-linux-android28','-mno-outline-atomics','-ffreestanding','-fPIC','-fno-stack-protector','-fno-builtin','-O2','-I'+str(inc),'-c',str(D/'native'/f'{n}.c'),'-o',str(obj)],
            [ld,'-shared' if n=='gralloc-bench' else '-pie','--no-undefined','--hash-style=both','--dynamic-linker=/system/bin/linker64','-L'+str(link),str(obj),'-lc','-llog','-lcutils','-ldl','-o',str(target)]]
        for cmd in commands:
            p=subprocess.run(cmd,capture_output=True,text=True);logs.append({'command':cmd,'exit_status':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
            if p.returncode:print(p.stderr);raise SystemExit(p.returncode)
        print('BUILT',target,target.stat().st_size)
    (D/'reports/native-build.local.json').write_text(json.dumps(logs,indent=2))
if __name__=='__main__':main()
