import numpy as np
from scipy.spatial.transform import Rotation

def alpha(cutoff,dt): return 1-np.exp(-2*np.pi*cutoff*dt)

class PoseFilter:
    """One Euro translation and angular-speed-adaptive quaternion SLERP."""
    def __init__(self, position_hz=1.5, position_beta=3., rotation_hz=2., rotation_beta=0.25, prediction_ms=15):
        self.pc=position_hz; self.pb=position_beta; self.rc=rotation_hz; self.rb=rotation_beta
        self.prediction=min(max(prediction_ms/1000,0),0.03); self.t=None; self.velocity=np.zeros(3);self.recovering=False
    def update(self,p,q,t):
        p=np.asarray(p,dtype=float); q=np.asarray(q,dtype=float)
        if p.shape!=(3,) or q.shape!=(4,) or not np.isfinite(np.r_[p,q,t]).all() or np.linalg.norm(q)<1e-8:
            raise ValueError('invalid filter pose')
        q=q/np.linalg.norm(q)
        if self.t is None:
            self.p=p.copy(); self.raw=p.copy(); self.q=q.copy(); self.t=t; self.velocity=np.zeros(3)
            return self.p.copy(), self.q.copy()
        dt=t-self.t
        if dt<=0: return self.p.copy(),self.q.copy()
        if dt>.35:
            self.raw=p.copy();self.velocity=np.zeros(3);self.recovering=True;dt=1/30
        dt=min(dt,1/15) # reacquisition must not teleport after a long loss
        velocity=(p-self.raw)/dt
        self.velocity+=alpha(1.,dt)*(velocity-self.velocity)
        step=alpha(self.pc+self.pb*np.linalg.norm(self.velocity),dt)*(p-self.p)
        speed_limit=1.5 if self.recovering else 6.
        step*=min(1.,speed_limit*dt/max(np.linalg.norm(step),1e-9))
        self.p+=step
        if np.dot(q,self.q)<0: q=-q
        delta=Rotation.from_quat(q)*Rotation.from_quat(self.q).inv()
        rv=delta.as_rotvec(); speed=np.linalg.norm(rv)/dt
        angle=np.linalg.norm(rv);fraction=min(alpha(self.rc+self.rb*speed,dt),6*dt/max(angle,1e-9))
        self.q=(Rotation.from_rotvec(rv*fraction)*Rotation.from_quat(self.q)).as_quat()
        self.raw=p.copy(); self.t=t
        if np.linalg.norm(p-self.p)<.05 and angle<.2:self.recovering=False
        # Bound prediction by 3cm even after a noisy reacquisition.
        pred=np.zeros(3) if self.recovering else self.velocity*self.prediction
        pred*=min(1.,0.03/max(np.linalg.norm(pred),1e-9))
        return self.p+pred,self.q.copy()
