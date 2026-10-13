import numpy as np
from scipy.spatial.transform import Rotation

# Neutral adult template in metres; personalize width AND lengths in config.
# Not a population-accurate measurement: template mismatch contributes uncertainty.
BASE=np.array([[.035,.025,0],[.0425,.085,0],[.012,.095,0],[-.018,.09,0],[-.0425,.075,0]])
LENGTHS=np.array([[.035,.025,.022],[.045,.027,.020],[.050,.030,.022],[.046,.028,.020],[.035,.022,.018]])

class Model:
    def __init__(self,palm_width_m=.085,bone_lengths_m=None):
        if not .045<=palm_width_m<=.13: raise ValueError('measure MCP breadth, metres')
        self.base=BASE*(palm_width_m/.085)
        self.lengths=LENGTHS*(palm_width_m/.085) if bone_lengths_m is None else np.asarray(bone_lengths_m)
        if self.lengths.shape!=(5,3) or not np.isfinite(self.lengths).all() or np.any(self.lengths<=0): raise ValueError('bone lengths')
    def local(self,angles,side):
        angles=np.asarray(angles).reshape(5,4) # splay, MCP, PIP, DIP radians
        points=[np.zeros(3)]
        for i,(spread,*flex) in enumerate(angles):
            p=self.base[i].copy(); points.append(p.copy())
            theta=0.
            # Thumb neutral abducts away from palm; other digits start longitudinal.
            azimuth=spread+(0.85 if i==0 else 0)
            for length,bend in zip(self.lengths[i],flex):
                theta+=bend
                p=p+length*np.array([np.sin(azimuth)*np.cos(theta),np.cos(azimuth)*np.cos(theta),np.sin(theta)])
                points.append(p.copy())
        points=np.array(points)
        if side==1: points[:,0]*=-1
        return points
    def forward(self,x,side): return Rotation.from_rotvec(x[3:6]).apply(self.local(x[6:],side))+x[:3]
    def forward_batch(self,x,side):
        """Evaluate all finite-difference perturbations together, no Python digit loop."""
        x=np.atleast_2d(x);a=x[:,6:].reshape(-1,5,4)
        theta=np.cumsum(a[:,:,1:],axis=2); az=a[:,:,0]+np.array([.85,0,0,0,0])
        direction=np.stack([np.sin(az)[:,:,None]*np.cos(theta),np.cos(az)[:,:,None]*np.cos(theta),np.sin(theta)],axis=-1)
        tips=self.base[None,:,None,:]+np.cumsum(direction*self.lengths[None,:,:,None],axis=2)
        digits=np.concatenate([np.broadcast_to(self.base[None,:,None,:],(len(x),5,1,3)),tips],axis=2)
        points=np.concatenate([np.zeros((len(x),1,3)),digits.reshape(-1,20,3)],axis=1)
        if side==1:points[:,:,0]*=-1
        r=Rotation.from_rotvec(x[:,3:6]).as_matrix()
        return np.einsum('nij,nkj->nki',r,points)+x[:,None,:3]

def project(points,k,distortion=None):
    fx,fy,cx,cy=k
    xy=points[:,:2]/np.maximum(points[:,2,None],.01)
    if distortion is not None:
        k1,k2,p1,p2,k3=distortion
        a,b=xy.T; r=a*a+b*b; radial=1+k1*r+k2*r*r+k3*r*r*r
        xy=np.stack([a*radial+2*p1*a*b+p2*(r+2*a*a), b*radial+p1*(r+2*b*b)+2*p2*a*b],axis=1)
    return xy*np.array([fx,fy])+[cx,cy]

def rays(uv,k,distortion=None):
    """Invert Brown-Conrady with fixed-point iterations; return z=1 rays."""
    fx,fy,cx,cy=k; observed=(np.asarray(uv)-[cx,cy])/[fx,fy]; xy=observed.copy()
    if distortion is not None:
        k1,k2,p1,p2,k3=distortion
        for _ in range(12):
            a,b=xy.T; r=a*a+b*b; radial=1+k1*r+k2*r*r+k3*r*r*r
            tang=np.stack([2*p1*a*b+p2*(r+2*a*a),p1*(r+2*b*b)+2*p2*a*b],axis=1)
            if np.any(np.abs(radial)<.1): raise ValueError('invalid lens calibration')
            xy=(observed-tang)/radial[:,None]
    return np.column_stack([xy,np.ones(len(xy))])
