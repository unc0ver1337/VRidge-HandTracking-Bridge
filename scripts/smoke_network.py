"""Real local Bonjour + UDP + MediaPipe decoder + GlassVR-wire smoke; synthetic source labelled.

Run from repo root: python -m scripts.smoke_network
Uses loopback only, no iPhone or SteamVR claim is implied.
"""
import json,socket,time
import numpy as np
from zeroconf import ServiceBrowser,Zeroconf,ServiceListener
from pc.network import Server,SERVICE
from pc.protocol import Frame,Hand,encode
from tests.geometry import Model,project
from pc.tracking.mediapipe import Decoder
from scipy.spatial.transform import Rotation
from pc.glassvr.adapter import GlassVR

class Listener(ServiceListener):
    def __init__(self):self.found=[]
    def add_service(self,zc,type_,name):self.found.append(name)
    def remove_service(self,zc,type_,name):self.found=[n for n in self.found if n!=name]
    def update_service(self,zc,type_,name):self.add_service(zc,type_,name)

def main():
    server=Server(port=39580,bind_ip='127.0.0.1',advertise_ip='127.0.0.1');server.start()
    zc=Zeroconf(interfaces=['127.0.0.1']);listener=Listener();browser=ServiceBrowser(zc,SERVICE,listener)
    phone=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);phone.bind(('127.0.0.1',0));phone.settimeout(3)
    sink=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);sink.bind(('127.0.0.1',0));sink.settimeout(2)
    glass=GlassVR(left_port=sink.getsockname()[1],right_port=sink.getsockname()[1]);dest=('127.0.0.1',39580)
    def send(obj):phone.sendto(json.dumps({'protocol':'MPBR','v':2}|obj).encode(),dest)
    try:
        deadline=time.monotonic()+3
        while not listener.found and time.monotonic()<deadline:time.sleep(.03)
        assert listener.found,'Bonjour not discovered'
        send({'type':'hello','nonce':'smoke-test-unique-nonce','device':'SYNTHETIC loopback client'})
        welcome=json.loads(phone.recv(2048));session=welcome['session']
        t0=time.monotonic();send({'type':'ping','session':session,'t0':t0});pong=json.loads(phone.recv(2048));t3=time.monotonic()
        send({'type':'sync','session':session,'t0':t0,'t3':t3,'s1':pong['s1'],'s2':pong['s2']});time.sleep(.05)
        model=Model();k=np.array([420,420,320,240]);x=np.r_[[0,0,.6],[np.pi,0,0],np.tile([0,.1,.1,.065],5)]
        joints=model.forward(x,2);uv=project(joints,k);hand=Hand(2,2,0,np.column_stack([uv/[640,480],np.ones(21)]),joints-joints[0],joints[0],Rotation.from_rotvec(x[3:6]).as_quat(),0.,True)
        frame=Frame(1,session,time.monotonic(),640,480,k,[hand]);phone.sendto(encode(frame),dest)
        deadline=time.monotonic()+2;item=None
        while item is None and time.monotonic()<deadline:item=server.take();time.sleep(.005)
        assert item is not None,'UDP frame not received'
        out=Decoder().decode(item[0].hands[0],2)
        glass.send(2,out.position,out.quaternion,{},out.angles)
        sizes=[len(sink.recv(512)) for _ in range(4)];assert sizes==[25,33,77,201]
        print(json.dumps({'source':'synthetic loopback; no physical hardware','bonjour':listener.found,'clock_rtt_ms':server.rtt*1000,'glassvr_packet_bytes':sizes,'reprojection_px':out.pixel_rmse,'solve_ms':out.solve_ms,'result':'PASS'},indent=2))
    finally:glass.close();phone.close();sink.close();browser.cancel();zc.close();server.close()

if __name__=='__main__':main()
