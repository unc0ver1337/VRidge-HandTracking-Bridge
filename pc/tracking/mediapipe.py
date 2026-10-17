"""Consume the on-phone MediaPipe 3D pose; no PC nonlinear reconstruction."""
import time
import numpy as np
from scipy.spatial.transform import Rotation
from .pose import Estimate

def bend(a,b):
    length=np.linalg.norm(a)*np.linalg.norm(b)
    if length<1e-8:raise ValueError('degenerate finger segment')
    return np.arccos(np.clip(np.dot(a,b)/length,-1,1))

class Decoder:
    def decode(self,hand,side):
        start=time.perf_counter()
        if not hand.pose_valid or hand.world is None:raise ValueError('phone pose unavailable')
        world=np.asarray(hand.world);p=np.asarray(hand.position);q=np.asarray(hand.quaternion)
        if side not in (1,2) or hand.side not in (0,1,2):raise ValueError('hand role')
        if world.shape!=(21,3) or p.shape!=(3,) or q.shape!=(4,):raise ValueError('MP geometry shape')
        if not np.isfinite(world).all() or not np.isfinite(np.r_[p,q,hand.reprojection]).all():raise ValueError('MP geometry')
        if not .08<=p[2]<=2.5 or abs(np.linalg.norm(q)-1)>.01 or not 0<=hand.reprojection<=20:raise ValueError('MP pose')
        rotation=Rotation.from_quat(q)
        if (hand.side==1)!=(side==1):rotation=rotation*Rotation.from_rotvec([0,np.pi,0])
        q=rotation.as_quat();local=rotation.inv().apply(world-world[0])
        if side==1:local[:,0]*=-1
        angles=np.zeros((5,4));valid=np.ones(5,dtype=bool)
        for digit in range(5):
            chain=local[1+4*digit:5+4*digit];a,b,c=np.diff(chain,axis=0)
            if min(np.linalg.norm(a),np.linalg.norm(b),np.linalg.norm(c))<1e-5:
                valid[digit]=False
                continue # One bad finger must not discard a valid controller pose.
            spread=np.arctan2(a[0],a[1])-(.85 if digit==0 else 0)
            angles[digit]=[np.clip(spread,-.61,.61),np.clip(np.arctan2(a[2],np.hypot(a[0],a[1])),-.15,1.66),bend(a,b),bend(b,c)]
        angles[:,2]=np.clip(angles[:,2],0,1.92);angles[:,3]=np.clip(angles[:,3],0,1.48)
        joints=world-world[0]+p;normal=rotation.apply([0,0,1]);facing='edge/uncertain' if abs(normal[2])<.25 else 'toward' if normal[2]<0 else 'away'
        return Estimate(p,q,joints,angles,hand.reprojection,.15*p[2],True,(time.perf_counter()-start)*1000,normal,facing,valid,hand.reprojection,False)
