import numpy as np
from scipy.spatial.transform import Rotation

# Synthetic test fixture only; never used to reconstruct runtime landmarks.
# Not a population-accurate measurement: template mismatch contributes uncertainty.
BASE=np.array([[.035,.025,0],[.0425,.085,0],[.012,.095,0],[-.018,.09,0],[-.0425,.075,0]])
LENGTHS=np.array([[.035,.025,.022],[.045,.027,.020],[.050,.030,.022],[.046,.028,.020],[.035,.022,.018]])

class Model:
    def __init__(self,palm_width_m=.085,bone_lengths_m=None):
        if not .045<=palm_width_m<=.13: raise ValueError('measure MCP breadth, metres')
        template_width=np.linalg.norm(BASE[1]-BASE[4])
        self.base=BASE*(palm_width_m/template_width)
        self.lengths=LENGTHS*(palm_width_m/template_width) if bone_lengths_m is None else np.asarray(bone_lengths_m)
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

def project(points,k,distortion=None):
    fx,fy,cx,cy=k
    xy=points[:,:2]/np.maximum(points[:,2,None],.01)
    if distortion is not None:
        k1,k2,p1,p2,k3=distortion
        a,b=xy.T; r=a*a+b*b; radial=1+k1*r+k2*r*r+k3*r*r*r
        xy=np.stack([a*radial+2*p1*a*b+p2*(r+2*a*a), b*radial+p1*(r+2*b*b)+2*p2*a*b],axis=1)
    return xy*np.array([fx,fy])+[cx,cy]
