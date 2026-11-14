"""Fetch only the three pinned ARM64 software rendering libraries, not another OS."""
from pathlib import Path
import hashlib,json,struct,subprocess,tempfile,urllib.request,zlib,sys
from config import load

D=Path(__file__).resolve().parent
URL='https://dl.google.com/android/repository/sys-img/android/arm64-v8a-29_r08.zip'

def request_range(start,end):
    request=urllib.request.Request(URL,headers={'Range':f'bytes={start}-{end}'})
    with urllib.request.urlopen(request,timeout=90)as f:
        if f.status!=206:raise RuntimeError('Server did not honor range request')
        result=f.read(64*1024*1024)
    return result

def main(offline=False):
    cfg=load()
    expected=json.loads((D/'scripts/dependencies/renderer.lock.json').read_text())['files']
    (D/'build').mkdir(exist_ok=True)
    def present():return all((D/'build'/name).exists()and hashlib.sha256((D/'build'/name).read_bytes()).hexdigest()==row['sha256']for name,row in expected.items())
    if not present():
        if offline:raise FileNotFoundError('Offline renderer cache missing')
        req=urllib.request.Request(URL,headers={'Range':'bytes=-65536'})
        with urllib.request.urlopen(req,timeout=30)as f:tail=f.read(65536)
        at=tail.rfind(b'PK\x05\x06');eocd=struct.unpack_from('<4s4H2IH',tail,at)
        cd=request_range(eocd[6],eocd[6]+eocd[5]-1);o=0;vendor=None
        while cd[o:o+4]==b'PK\x01\x02':
            h=struct.unpack_from('<4s6H3I5H2I',cd,o);name=cd[o+46:o+46+h[10]].decode()
            if name=='arm64-v8a/vendor.img':vendor={'compressed':h[8],'size':h[9],'crc32':h[7],'offset':h[-1]}
            o+=46+h[10]+h[11]+h[12]
        if not vendor:raise RuntimeError('vendor entry missing')
        h=struct.unpack_from('<4s5H3I2H',request_range(vendor['offset'],vendor['offset']+255))
        start=vendor['offset']+30+h[-2]+h[-1]
        compressed=request_range(start,start+vendor['compressed']-1)
        data=zlib.decompress(compressed,-15)
        assert len(data)==vendor['size']and zlib.crc32(data)&0xffffffff==vendor['crc32']
        offset=data.find(b'\x53\xef')-1080
        if offset!=1048576:raise RuntimeError('Unexpected partition offset')
        with tempfile.TemporaryDirectory(prefix='android-renderer-')as td:
            image=Path(td)/'vendor.ext4';image.write_bytes(data[offset:])
            for name,row in expected.items():
                target=D/'build'/name
                p=subprocess.run([cfg['node'],str(D/'tools/extract_ext4_sparse.js'),str(image),'extract','/lib64/egl/'+name,str(target)],capture_output=True)
                assert p.returncode==0,p.stderr
                assert hashlib.sha256(target.read_bytes()).hexdigest()==row['sha256']
        print('Downloaded vendor member only:',len(compressed),'bytes; temporary vendor removed')
    assert present()
    link=D/'build/link';link.mkdir(exist_ok=True)
    if not (Path(cfg['firmware_dir'])/'system.img').is_file():
        print('Public renderer prepared. Supply firmware system.img before compiling the HAL.')
        return False
    for name in ['libc.so','liblog.so','libhardware.so','libcutils.so','libsync.so','libdl.so']:
        target=link/name
        if not target.exists():
            p=subprocess.run([cfg['node'],str(D/'tools/extract_ext4_sparse.js'),str(Path(cfg['firmware_dir'])/'system.img'),'extract','/system/lib64/'+name,str(target)],capture_output=True)
            assert p.returncode==0,p.stderr
    print('PASS software renderer hashes; private firmware link inputs remain local')
    return True

if __name__=='__main__':main()
