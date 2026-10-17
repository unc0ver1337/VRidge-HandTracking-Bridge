import json,logging,secrets,socket,threading,time,uuid,ipaddress
from collections import deque
from .protocol import decode,Sequence,VERSION
from .interfaces import local_ipv4

LOG=logging.getLogger(__name__)
SERVICE='_mpbridge._udp.local.'

class Server:
    """Dedicated bounded receiver. Last-frame replacement never builds a queue."""
    def __init__(self,port=39580,timeout_s=3,bind_ip='0.0.0.0',advertise_ip=None):
        self.port=port; self.timeout=timeout_s; self.bind_ip=bind_ip; self.advertise_ip=advertise_ip
        self.stop=threading.Event(); self.lock=threading.Lock(); self.latest=None
        self.peer=None; self.session=0; self.last_seen=0; self.seq=Sequence(); self.offset=None; self.rtt=float('inf')
        self.invalid=0; self.replaced=0; self.clock_rejected=0
        self.clock_samples=deque(maxlen=120);self.registered=False
        self.announcements={}
    def start(self):
        from zeroconf import Zeroconf,ServiceInfo
        self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); self.sock.bind((self.bind_ip,self.port)); self.sock.settimeout(.2)
        self.announce_thread=threading.Thread(target=self.watch_interfaces,name='discovery-interfaces',daemon=True);self.announce_thread.start()
        self.thread=threading.Thread(target=self.run,name='network',daemon=True); self.thread.start()
        LOG.info('UDP listening %s:%d; discovery on every IPv4 adapter',self.bind_ip,self.port)
    def refresh_interfaces(self):
        from zeroconf import Zeroconf,ServiceInfo,IPVersion
        wanted=set(local_ipv4(self.advertise_ip,self.bind_ip))
        for ip in set(self.announcements)-wanted:
            zc,service=self.announcements.pop(ip)
            try:zc.unregister_service(service)
            finally:zc.close()
        for ip in sorted(wanted-set(self.announcements),key=lambda value:(ipaddress.ip_address(value).is_link_local,value)):
            if self.stop.is_set():break
            zc=None
            try:
                zc=Zeroconf(interfaces=[ip],ip_version=IPVersion.V4Only)
                # Separate names/host records prevent an iPhone on the hotspot
                # from receiving the unrelated Ethernet/VPN address first.
                suffix=ip.replace('.','-')
                service=ServiceInfo(SERVICE,'GlassVR iPhone Bridge '+suffix+'.'+SERVICE,addresses=[socket.inet_aton(ip)],port=self.port,properties={'protocol':'MPBR','version':str(VERSION),'instance':str(uuid.uuid4())},server='mpbridge-'+suffix+'.local.')
                zc.register_service(service);self.announcements[ip]=(zc,service)
                LOG.info('Bonjour enabled on %s:%d',ip,self.port)
            except Exception as error:
                if zc:zc.close()
                LOG.warning('Discovery unavailable on %s: %s; retrying',ip,error)
    def watch_interfaces(self):
        while not self.stop.is_set():
            try:self.refresh_interfaces()
            except Exception:LOG.exception('Interface refresh failed; will retry')
            self.stop.wait(5)
    def send(self,obj,addr): self.sock.sendto(json.dumps(obj,separators=(',',':')).encode(),addr)
    def control(self,msg,addr,now):
        if msg.get('v')!=VERSION or msg.get('protocol')!='MPBR': raise ValueError('control protocol')
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
            self.send({'protocol':'MPBR','v':VERSION,'type':'welcome','nonce':nonce,'session':self.session},addr)
        elif addr==self.peer and msg.get('session')==self.session:
            if kind=='ping':
                self.last_seen=now
                self.send({'protocol':'MPBR','v':VERSION,'type':'pong','session':self.session,'t0':float(msg['t0']),'s1':now,'s2':time.monotonic()},addr)
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
        if hasattr(self,'announce_thread'):self.announce_thread.join(8)
        if hasattr(self,'sock'):self.sock.close()
        for zc,service in list(self.announcements.values()):
            try:
                zc.unregister_service(service)
            finally:zc.close()
        self.announcements.clear()
