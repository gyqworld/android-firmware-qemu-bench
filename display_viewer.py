"""Live pixels from Android's framebuffer HAL, never a recreated application UI."""
import io,json,socket,struct,threading,time,hashlib,subprocess,sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from config import load
PACKAGES=Path(__file__).resolve().parent/'runtime/python-packages'
if PACKAGES.is_dir():sys.path.insert(0,str(PACKAGES))
from PIL import Image

HTML='''<!doctype html><meta charset="utf-8"><title>Original Android — live framebuffer</title>
<style>body{margin:0;background:#181818;color:#ddd;font:14px sans-serif}header{padding:8px}canvas{max-width:100vw;max-height:90vh;touch-action:none;background:#000;display:block;margin:auto}</style>
<header id="status">Waiting for actual Android frames…</header><canvas id="c" width="800" height="480"></canvas>
<script>const c=document.getElementById('c'),ctx=c.getContext('2d');let seq=-1,down;
async function update(){try{let s=await(await fetch('/state')).json();document.getElementById('status').textContent='Original Android live | received '+s.frames+' frames | '+(s.width||800)+'×'+(s.height||480);if(s.frames!==seq&&s.frames){let b=await(await fetch('/frame')).blob(),im=await createImageBitmap(b);c.width=im.width;c.height=im.height;ctx.drawImage(im,0,0);im.close();seq=s.frames;}}catch(e){}setTimeout(update,150)}update();
function xy(e){let r=c.getBoundingClientRect();return{x:Math.round((e.clientX-r.left)*c.width/r.width),y:Math.round((e.clientY-r.top)*c.height/r.height)}}
c.onpointerdown=e=>{down=xy(e);c.setPointerCapture(e.pointerId)};c.onpointerup=e=>{if(!down)return;let p=xy(e);fetch('/input',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({x:down.x,y:down.y,x2:p.x,y2:p.y})});down=null};</script>'''

class FrameViewer:
    def __init__(self,port,output):
        self.port=port;self.output=Path(output);self.closed=False;self.png=b'';self.state={'frames':0,'source':'Android gralloc framebuffer post','synthetic':False};self.lock=threading.Lock()
        owner=self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.headers.get('Host') != f'127.0.0.1:{owner.http.server_port}':
                    self.send_error(403);return
                if self.path=='/state':b=json.dumps(owner.state).encode();kind='application/json'
                elif self.path=='/frame':b=owner.png;kind='image/png'
                else:b=HTML.encode();kind='text/html; charset=utf-8'
                self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
            def do_POST(self):
                try:
                    expected=f'http://127.0.0.1:{owner.http.server_port}'
                    if self.path!='/input' or self.headers.get('Host')!=expected.removeprefix('http://'):
                        raise ValueError('Host/path')
                    if self.headers.get('Origin') not in (None, expected):
                        raise ValueError('Cross-origin input')
                    if not self.headers.get('Content-Type','').startswith('application/json'):
                        raise ValueError('JSON required')
                    p=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length','0')),2048)))
                    v=[int(p[n])for n in ['x','y','x2','y2']]
                    if not all(0<=n<=4096 for n in v):raise ValueError()
                    command=(f'input tap {v[0]} {v[1]}' if abs(v[0]-v[2])+abs(v[1]-v[3])<10 else f'input swipe {v[0]} {v[1]} {v[2]} {v[3]} 400')
                    threading.Thread(target=lambda:subprocess.run([sys.executable,str(Path(__file__).with_name('control.py')),command,'--timeout','20'],capture_output=True),daemon=True).start()
                    self.send_response(204)
                except Exception:self.send_response(400)
                self.end_headers()
            def log_message(self,*args):pass
        self.http=ThreadingHTTPServer(('127.0.0.1',0),Handler);self.url=f'http://127.0.0.1:{self.http.server_port}/'
        threading.Thread(target=self.http.serve_forever,daemon=True).start();threading.Thread(target=self.receive,daemon=True).start()
    def receive(self):
        s=None
        for i in range(100):
            if self.closed:return
            try:s=socket.create_connection(('127.0.0.1',self.port),timeout=2);break
            except OSError:time.sleep(.1)
        if s is None:return
        self.socket=s;s.settimeout(2)
        def recv(n):
            b=bytearray()
            while len(b)<n and not self.closed:
                try:q=s.recv(n-len(b))
                except socket.timeout:continue
                if not q:raise EOFError()
                b.extend(q)
            if len(b)!=n:raise EOFError()
            return bytes(b)
        try:
            while not self.closed:
                magic,w,h,stride,fmt,n,seq,_=struct.unpack('<8I',recv(32))
                if magic!=0x4d524642 or not(0<w<=4096 and 0<h<=4096 and n<=64*1024*1024):raise ValueError('Frame header')
                data=recv(n)
                raw={1:'RGBA',2:'RGBX',3:'RGB',4:'BGR;16',5:'BGRA'}.get(fmt)
                if raw is None:raise ValueError(f'Pixel format {fmt}')
                img=Image.frombytes('RGBA' if fmt in (1,5)else'RGB',(w,h),data,'raw',raw,stride*({4:2,3:3}.get(fmt,4)),1)
                b=io.BytesIO();img.save(b,format='PNG');self.png=b.getvalue()
                self.state.update(frames=self.state['frames']+1,width=w,height=h,format=fmt,last_sequence=seq,last_pixel_sha256=hashlib.sha256(data).hexdigest(),last_host_time=time.time())
                history=self.state.setdefault('recent_pixel_sha256',[])
                if not history or history[-1]!=self.state['last_pixel_sha256']:
                    history.append(self.state['last_pixel_sha256']);del history[:-64]
                (self.output/'display-state.json').write_text(json.dumps(self.state,indent=2))
        except Exception as e:
            if not self.closed:self.state['transport_error']=repr(e)
        finally:s.close()
    def close(self):
        self.closed=True
        if hasattr(self,'socket'):self.socket.close()
        self.http.shutdown();self.http.server_close()
        (self.output/'display-state.json').write_text(json.dumps(self.state,indent=2))
