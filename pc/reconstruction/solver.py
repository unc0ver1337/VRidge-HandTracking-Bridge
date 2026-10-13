from dataclasses import dataclass
import time
import numpy as np
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation
from .model import Model,project,rays

@dataclass
class Estimate:
    position: np.ndarray
    quaternion: np.ndarray # xyzw
    joints: np.ndarray
    angles: np.ndarray
    pixel_rmse: float
    depth_sigma_m: float
    orientation_ambiguous: bool
    solve_ms: float

class Solver:
    def __init__(self,palm_width_m=.085,bone_lengths_m=None,distortion=None,max_evaluations=22):
        self.model=Model(palm_width_m,bone_lengths_m); self.distortion=distortion
        self.previous={}; self.max_eval=max_evaluations
        # Splay +/-35deg, MCP up to95, PIP110, DIP85. Thumb uses same conservative bounds.
        self.low=np.r_[[-3,-3,.08],[-2*np.pi]*3,np.tile([-.61,-.15,0,0],5)]
        self.high=np.r_[[3,3,2.5],[2*np.pi]*3,np.tile([.61,1.66,1.92,1.48],5)]
    def initial(self,uv,k,side):
        r=rays(uv,k,self.distortion)
        depth=np.clip(np.linalg.norm(self.model.base[1]-self.model.base[4])/max(np.linalg.norm(r[5]-r[17]),.02),.12,2.)
        xaxis=r[5]-r[17]; xaxis*=(-1 if side==1 else 1); xaxis/=max(np.linalg.norm(xaxis),1e-9)
        yaxis=r[9]-r[0]; yaxis-=xaxis*np.dot(xaxis,yaxis); yaxis/=max(np.linalg.norm(yaxis),1e-9)
        zaxis=np.cross(xaxis,yaxis)
        if np.linalg.norm(zaxis)<.5: raise ValueError('degenerate palm')
        rot=Rotation.from_matrix(np.column_stack([xaxis,yaxis,zaxis])).as_rotvec()
        return np.r_[r[0]*depth,rot,np.zeros(20)]
    def solve(self,hand,frame,side):
        start=time.perf_counter(); uv=hand.points[:,:2]*[frame.width,frame.height]; c=hand.points[:,2]
        if np.count_nonzero(c>.3)<8 or np.count_nonzero(c[[0,5,9,13,17]]>.3)<3: raise ValueError('insufficient landmarks')
        old=self.previous.get(side); dt=frame.capture-old[1] if old else 100.
        continuous=old is not None and 0<dt<.35
        initial=old[0].copy() if continuous else self.initial(uv,frame.intrinsics,side)
        weights=np.sqrt(np.clip(c,0,1))[:,None]/2. # nominal 2 pixel measurement sigma
        def residual(x):
            points=self.model.forward(x,side)
            reproj=((project(points,frame.intrinsics,self.distortion)-uv)*weights).ravel()
            anatomical=(x[6:].reshape(5,4)[:,3]-.65*x[6:].reshape(5,4)[:,2])/.5
            behind=np.minimum(points[:,2]-.04,0)*1000
            if continuous:
                delta=(Rotation.from_rotvec(x[3:6])*Rotation.from_rotvec(old[0][3:6]).inv()).as_rotvec()
                temporal=np.r_[(x[:3]-old[0][:3])/(.015+dt),delta/(.15+3*dt),(x[6:]-old[0][6:])/(.35+6*dt)]
            else: temporal=(x-initial)/np.r_[[1,1,1],[3,3,3],[4]*20]
            return np.r_[reproj,anatomical,behind,temporal]
        starts=[initial]
        if not continuous:
            # Competing depth/tilt branch. A single view cannot always distinguish it.
            alternate=initial.copy()
            alternate[3:6]=(Rotation.from_rotvec(initial[3:6])*Rotation.from_rotvec([.65,0,0])).as_rotvec()
            starts.append(alternate)
        fits=[least_squares(residual,np.clip(x,self.low+1e-6,self.high-1e-6),bounds=(self.low,self.high),loss='soft_l1',f_scale=2.,max_nfev=self.max_eval) for x in starts]
        fit=min(fits,key=lambda f:np.sum(residual(f.x)**2)); points=self.model.forward(fit.x,side)
        error=np.linalg.norm(project(points,frame.intrinsics,self.distortion)-uv,axis=1)
        rmse=np.sqrt(np.average(error**2,weights=c))
        if not np.isfinite(fit.x).all() or rmse>18 or np.any(points[:,2]<.04): raise ValueError('pose rejected: reprojection/cheirality')
        # Local covariance is optimistic for monocular scale ambiguity. Enforce 15%
        # scale uncertainty floor until a measured personal template is available.
        cov=np.linalg.pinv(fit.jac.T@fit.jac,rcond=1e-7)
        sigma=max(np.sqrt(max(cov[2,2],0)),.15*fit.x[2])
        self.previous[side]=(fit.x.copy(),frame.capture)
        return Estimate(fit.x[:3],Rotation.from_rotvec(fit.x[3:6]).as_quat(),points,fit.x[6:].reshape(5,4),rmse,sigma,True,(time.perf_counter()-start)*1000)
