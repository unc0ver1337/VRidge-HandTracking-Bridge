import json,logging,secrets,socket,threading,time,uuid
from collections import deque
from .protocol import decode,Sequence,VERSION

LOG=logging.getLogger(__name__)
SERVICE='_vhbridge._udp.local.'

class Server:
    """Dedicated bounded receiver. Last-frame replacement never builds a queue."""
    def __init__(self,port=39570,timeout_s=3,bind_ip='0.0.0.0',advertise_ip=None):
        self.port=port; self.timeout=timeout_s; self.bind_ip=bind_ip; self.advertise_ip=advertise_ip
        self.stop=threading.Event(); self.lock=threading.Lock(); self.latest=None
        self.peer=None; self.session=0; self.last_seen=0; self.seq=Sequence(); self.offset=None; self.rtt=float('inf')
        self.invalid=0; self.replaced=0; self.clock_rejected=0
        self.clock_samples=deque(maxlen=120);self.registered=False
    def start(self):
        from zeroconf import Zeroconf,ServiceInfo
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); self.sock.bind((self.bind_ip,self.port)); self.sock.settimeout(.2)
        if self.advertise_ip: ip=self.advertise_ip
        else:
            # Route lookup chooses the LAN address without sending a datagram.
            with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as route:
                route.connect(('192.0.2.1',9)); ip=route.getsockname()[0]
        self.zc=Zeroconf(interfaces=[ip])
        self.service=ServiceInfo(SERVICE,'GlassVR iPhone Bridge.'+SERVICE,addresses=[socket.inet_aton(ip)],port=self.port,properties={'protocol':'VHBR','version':str(VERSION),'instance':str(uuid.uuid4())},server=socket.gethostname()+'.local.')
        self.zc.register_service(self.service)
        self.registered=True
        self.thread=threading.Thread(target=self.run,name='network',daemon=True); self.thread.start()
        LOG.info('Bonjour GlassVR iPhone Bridge %s:%d',ip,self.port)
    def send(self,obj,addr): self.sock.sendto(json.dumps(obj,separators=(',',':')).encode(),addr)
    def control(self,msg,addr,now):
        if msg.get('v')!=VERSION or msg.get('protocol')!='VHBR': raise ValueError('control protocol')
        kind=msg.get('type')
        if kind=='hello':
            nonce=msg.get('nonce','')
            if not isinstance(nonce,str) or not 16<=len(nonce)<=64: raise ValueError('nonce')
            if self.peer and addr!=self.peer and now-self.last_seen<self.timeout: return
            if self.peer!=addr or msg.get('nonce')!=getattr(self,'nonce',None):
                self.session=secrets.randbits(52)+1; self.peer=addr; self.seq=Sequence(); self.offset=None; self.rtt=float('inf'); self.nonce=nonce;self.clock_samples.clear()
                with self.lock: self.latest=None
                LOG.info('iPhone %s at %s',str(msg.get('device','unknown'))[:80],addr)
            self.last_seen=now
            self.send({'protocol':'VHBR','v':VERSION,'type':'welcome','nonce':nonce,'session':self.session},addr)
        elif addr==self.peer and msg.get('session')==self.session:
            if kind=='ping':
                self.last_seen=now
                self.send({'protocol':'VHBR','v':VERSION,'type':'pong','session':self.session,'t0':float(msg['t0']),'s1':now,'s2':time.monotonic()},addr)
            elif kind=='sync':
                t0,t3,s1,s2=[float(msg[k]) for k in ('t0','t3','s1','s2')]
                import math
                if not all(math.isfinite(x) for x in (t0,t3,s1,s2)): raise ValueError('clock')
                rtt=(t3-t0)-(s2-s1)
                if not 0<=rtt<.5 or abs(now-s2)>.5: raise ValueError('clock interval')
                self.clock_samples.append((now,rtt,((s1-t0)+(s2-t3))/2))
                while self.clock_samples and now-self.clock_samples[0][0]>60:self.clock_samples.popleft()
                _,self.rtt,self.offset=min(self.clock_samples,key=lambda item:item[1])
    def ingest(self,data,addr,now):
        if data.startswith(b'{'):
            self.control(json.loads(data),addr,now); return
        if addr!=self.peer or self.offset is None: return
        frame=decode(data)
        if frame.session!=self.session: return
        age=now-(frame.capture+self.offset)
        if age<-.03 or age>.2: self.clock_rejected+=1; return
        if not self.seq.accept(frame.seq): return
        self.last_seen=now
        with self.lock:
            if self.latest: self.replaced+=1
            self.latest=(frame,frame.capture+self.offset,now)
    def run(self):
        while not self.stop.is_set():
            try:
                raw,addr=self.sock.recvfrom(2048); self.ingest(raw,addr,time.monotonic())
            except socket.timeout: continue
            except (ValueError,KeyError,TypeError,OverflowError): self.invalid+=1
            except OSError:
                if not self.stop.is_set(): LOG.exception('network error')
    def take(self):
        with self.lock: result=self.latest; self.latest=None
        return result
    def close(self):
        self.stop.set()
        if hasattr(self,'thread'):self.thread.join(1)
        if hasattr(self,'sock'):self.sock.close()
        if hasattr(self,'zc'):
            try:
                if self.registered:self.zc.unregister_service(self.service)
            finally:self.zc.close()
