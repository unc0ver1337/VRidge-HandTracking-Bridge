import socket,struct
import numpy as np

def packets(position,quaternion,buttons,angles):
    p=np.asarray(position); q=np.asarray(quaternion)
    if p.shape!=(3,) or q.shape!=(4,) or not np.isfinite(np.r_[p,q]).all() or np.linalg.norm(q)<1e-6: raise ValueError('pose')
    q=q/np.linalg.norm(q)
    digital=['a','b','system','joy_btn','trigger_btn','a_cap','b_cap','system_cap','joy_cap','trigger_cap','touch_cap','grip_cap']
    analog=['joy_x','joy_y','touch_x','touch_y','trigger','touch_force','grip_pull','grip_force']
    values=[float(buttons.get(k,0)) for k in analog]
    if not np.isfinite(values).all(): raise ValueError('input')
    values=[float(np.clip(v,-1 if i<4 else 0,1)) for i,v in enumerate(values)]
    a=np.asarray(angles)
    if a.shape!=(5,4) or not np.isfinite(a).all(): raise ValueError('angles')
    curls=np.zeros(20)
    # Upstream simulation: generic MCP/PIP/DIP = curl * [90,80,80] degrees;
    # thumb = [5,90,90]. Least-squares inverse fits those actual driver gains.
    gains=np.deg2rad(np.array([[5,90,90]]+[[90,80,80]]*4))
    curls[::4]=np.clip(np.sum(a[:,1:]*gains,axis=1)/np.sum(gains*gains,axis=1),0,1)
    # GlassVR's splay unit is a multiplier of 20 degrees, not radians.
    splay=a[:,0]/np.deg2rad(20)
    # Upstream skeletal simulation consumes only indices 0,4,8,12,16.
    return [struct.pack('<c3d',b'P',*p),struct.pack('<c4d',b'R',q[3],*q[:3]),
            struct.pack('<c12?8d',b'I',*[bool(buttons.get(k,False)) for k in digital],*values),
            struct.pack('<c25d',b'S',*curls,*splay)]

class GlassVR:
    def __init__(self,host='127.0.0.1',left_port=9001,right_port=9002):
        if host not in ('127.0.0.1','localhost'): raise ValueError('GlassVR adapter must be loopback')
        self.dest={1:(host,left_port),2:(host,right_port)}; self.sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    def send(self,side,p,q,buttons,angles,include_input=True):
        for data in packets(p,q,buttons,angles):
            if include_input or data[:1]!=b'I':self.sock.sendto(data,self.dest[side])
    def input_only(self,side,buttons):
        data=packets([0,0,0],[0,0,0,1],buttons,np.zeros((5,4)))[2]
        self.sock.sendto(data,self.dest[side])
    def close(self):
        for side in (1,2): self.input_only(side,{})
        self.sock.close()
