from dataclasses import dataclass
from types import SimpleNamespace
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
    palm_normal: np.ndarray
    palm_facing: str
    finger_valid: np.ndarray = None
    palm_rmse: float = 0.

class Solver:
    def __init__(self,palm_width_m=.085,bone_lengths_m=None,distortion=None,max_evaluations=22,warm_max_evaluations=8):
        self.model=Model(palm_width_m,bone_lengths_m); self.distortion=distortion
        self.palm_templates={s:self.model.local(np.zeros((5,4)),s)[[0,5,9,13,17]] for s in (1,2)}
        self.previous={}; self.max_eval=max_evaluations;self.warm_max_eval=warm_max_evaluations
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
        if not np.isfinite(hand.points).all() or not np.isfinite(frame.intrinsics).all():raise ValueError('nonfinite landmarks or camera')
        if np.count_nonzero(c>.3)<8 or np.count_nonzero(c[[0,5,9,13,17]]>.3)<3: raise ValueError('insufficient landmarks')
        old=self.previous.get(side); dt=frame.capture-old[1] if old else 100.
        continuous=old is not None and 0<dt<.35
        initial=old[0].copy() if continuous else self.initial(uv,frame.intrinsics,side)
        weights=np.sqrt(np.clip(c,0,1))[:,None]/2. # nominal 2 pixel measurement sigma
        def batch_residual(x):
            x=np.atleast_2d(x);points=self.model.forward_batch(x,side)
            projected=project(points.reshape(-1,3),frame.intrinsics,self.distortion).reshape(-1,21,2)
            reproj=((projected-uv)*weights).reshape(len(x),42)
            angles=x[:,6:].reshape(-1,5,4)
            anatomical=(angles[:,:,3]-.65*angles[:,:,2])/.5
            behind=np.minimum(points[:,:,2]-.04,0)*1000
            normal=Rotation.from_rotvec(x[:,3:6]).as_matrix()[:,:,2]
            # Optional winding cue, deliberately weaker than a 2-pixel landmark.
            facing=np.maximum(0,-hand.palm*normal[:,2:3])*.5
            if continuous:
                delta=(Rotation.from_rotvec(x[:,3:6])*Rotation.from_rotvec(old[0][3:6]).inv()).as_rotvec()
                temporal=np.concatenate([(x[:,:3]-old[0][:3])/(.015+dt),delta/(.15+3*dt),(x[:,6:]-old[0][6:])/(.35+6*dt)],axis=1)
            else: temporal=(x-initial)/np.r_[[1,1,1],[3,3,3],[4]*20]
            return np.concatenate([reproj,anatomical,behind,facing,temporal],axis=1)
        def residual(x):return batch_residual(x)[0]
        # Rigid palm anchors cannot move when fingers bend. Fit the six rigid
        # parameters from these alone, then fit articulation with pose fixed.
        anchors=np.array([0,5,9,13,17])
        palm_local=self.palm_templates[side]
        def palm_batch(v):
            v=np.atleast_2d(v);rot=Rotation.from_rotvec(v[:,3:])
            pts=np.einsum('nij,kj->nki',rot.as_matrix(),palm_local)+v[:,None,:3]
            proj=project(pts.reshape(-1,3),frame.intrinsics,self.distortion).reshape(-1,5,2)
            reproj=((proj-uv[anchors])*weights[anchors]).reshape(len(v),10)
            if continuous:
                dr=(rot*Rotation.from_rotvec(old[0][3:6]).inv()).as_rotvec()
                prior=np.c_[(v[:,:3]-old[0][:3])/(.015+dt),dr/(.15+3*dt)]
            else:prior=(v-initial[:6])/np.array([1,1,1,3,3,3])
            return np.c_[reproj,prior,np.minimum(pts[:,:,2]-.04,0)*1000]
        def palm_residual(v):return palm_batch(v)[0]
        def palm_jac(v):
            step=1e-5;d=np.eye(6)*step;r=palm_batch(np.r_[v+d,v-d])
            return ((r[:6]-r[6:])/(2*step)).T
        def fit_candidate(seed):
            palm=least_squares(palm_residual,np.clip(seed[:6],self.low[:6]+1e-6,self.high[:6]-1e-6),
                jac=palm_jac,bounds=(self.low[:6],self.high[:6]),loss='soft_l1',f_scale=2.,max_nfev=budget)
            fixed=seed.copy();fixed[:6]=palm.x
            def residual_angles(a):
                x=fixed.copy();x[6:]=a;return batch_residual(x)[0]
            def finger_jacobian(a):
                step=1e-5;d=np.eye(20)*step
                x=np.broadcast_to(fixed,(40,26)).copy()
                x[:20,6:]=a+d;x[20:,6:]=a-d
                r=batch_residual(x)
                return ((r[:20]-r[20:])/(2*step)).T
            fingers=least_squares(residual_angles,np.clip(seed[6:],self.low[6:]+1e-6,self.high[6:]-1e-6),
                jac=finger_jacobian,bounds=(self.low[6:],self.high[6:]),loss='soft_l1',f_scale=2.,max_nfev=min(budget,4) if continuous else budget)
            if not continuous:
                bent=np.tile([0,.6,.9,.6],5)
                alternative=least_squares(residual_angles,bent,jac=finger_jacobian,
                    bounds=(self.low[6:],self.high[6:]),loss='soft_l1',f_scale=2.,max_nfev=budget)
                if np.sum(residual_angles(alternative.x)**2)<np.sum(residual_angles(fingers.x)**2):fingers=alternative
            fixed[6:]=fingers.x
            return SimpleNamespace(x=fixed,jac=palm.jac)
        starts=[initial]
        if not continuous:
            # Competing depth/tilt branch. A single view cannot always distinguish it.
            alternate=initial.copy()
            alternate[3:6]=(Rotation.from_rotvec(initial[3:6])*Rotation.from_rotvec([.65,0,0])).as_rotvec()
            starts.append(alternate)
        budget=min(self.max_eval,self.warm_max_eval) if continuous else self.max_eval
        fits=[fit_candidate(x) for x in starts]
        fit=min(fits,key=lambda f:np.sum(residual(f.x)**2)); points=self.model.forward(fit.x,side)
        error=np.linalg.norm(project(points,frame.intrinsics,self.distortion)-uv,axis=1)
        rmse=np.sqrt(np.average(error**2,weights=c))
        palm_rmse=np.sqrt(np.average(error[anchors]**2,weights=np.maximum(c[anchors],1e-9)))
        if not np.isfinite(fit.x).all() or palm_rmse>12 or np.any(points[anchors,2]<.04):raise ValueError('pose rejected: palm reprojection/cheirality')
        finger_valid=np.ones(5,dtype=bool)
        for finger in range(5):
            idx=np.arange(2+4*finger,5+4*finger);visible=c[idx]>.3
            good=np.count_nonzero(visible)>=2 and np.sqrt(np.average(error[idx]**2,weights=np.maximum(c[idx],1e-9)))<=18 and np.all(points[idx,2]>.04)
            if not good:
                finger_valid[finger]=False
                fit.x[6+4*finger:10+4*finger]=(old[0] if continuous else initial)[6+4*finger:10+4*finger]
        points=self.model.forward(fit.x,side)
        error=np.linalg.norm(project(points,frame.intrinsics,self.distortion)-uv,axis=1)
        rmse=np.sqrt(np.average(error**2,weights=c))
        # Local covariance is optimistic for monocular scale ambiguity. Enforce 15%
        # scale uncertainty floor until a measured personal template is available.
        cov=np.linalg.pinv(fit.jac.T@fit.jac,rcond=1e-7)
        sigma=max(np.sqrt(max(cov[2,2],0)),.15*fit.x[2])
        self.previous[side]=(fit.x.copy(),frame.capture)
        rotation=Rotation.from_rotvec(fit.x[3:6]);normal=rotation.apply([0,0,1])
        facing='edge/uncertain' if abs(normal[2])<.25 else 'toward' if normal[2]<0 else 'away'
        return Estimate(fit.x[:3],rotation.as_quat(),points,fit.x[6:].reshape(5,4),rmse,sigma,True,(time.perf_counter()-start)*1000,normal,facing,finger_valid,float(palm_rmse))
