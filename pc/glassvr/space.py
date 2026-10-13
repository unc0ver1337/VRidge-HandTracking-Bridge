import threading,time,logging
from collections import deque
import numpy as np
from scipy.spatial.transform import Rotation

def correct_head_relative_yaw(rotation,invert=False):
    """Change only yaw in HMD axes, retaining pitch and longitudinal roll.

    Intrinsic Y-X-Z: yaw around head up, then pitch, then controller roll.
    This is an orientation correction, never a mirror of metric hand positions.
    """
    if not invert:return rotation
    matrix=rotation.as_matrix()
    horizontal=np.hypot(matrix[0,2],matrix[2,2])
    if horizontal<1e-6:return rotation # yaw is undefined when pointing exactly vertical
    yaw=np.arctan2(matrix[0,2],matrix[2,2])
    return Rotation.from_rotvec([0,-2*yaw,0])*rotation

class Space:
    """Timestamped HMD history + measured rigid camera mount. SteamVR metres.

    Camera: +X right,+Y down,+Z forward. OpenVR: +X right,+Y up,-Z forward.
    Camera mount translation is the camera centre expressed in HMD coordinates.
    Driver UDP poses are RAW tracking coordinates. SteamVR applies its room/standing
    transform afterwards; using Standing HMD samples here would apply it twice.
    """
    def __init__(self,config):
        self.config=config; self.history=deque(maxlen=300); self.stop=threading.Event(); self.lock=threading.Lock()
        self.mount=Rotation.from_euler('xyz',config['camera_rotation_deg'],degrees=True).as_matrix()@np.diag([1,-1,-1])
        self.offset=np.asarray(config['camera_offset_m'],float); self.static=config['mode']=='static'
        self.origin=np.array(config.get('static_origin_m',[0,1.6,0]),float)
    def start(self):
        if not self.static:
            self.thread=threading.Thread(target=self.poll,name='openvr',daemon=True); self.thread.start()
    def poll(self):
        import openvr
        initialized=False
        while not self.stop.is_set():
            try:
                if not initialized: openvr.init(openvr.VRApplication_Background); initialized=True
                poses=openvr.VRSystem().getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseRawAndUncalibrated,0,openvr.k_unMaxTrackedDeviceCount)
                hmd=poses[openvr.k_unTrackedDeviceIndex_Hmd]
                if hmd.bPoseIsValid and hmd.bDeviceIsConnected:
                    m=np.array(hmd.mDeviceToAbsoluteTracking.m,dtype=float)
                    with self.lock: self.history.append((time.monotonic(),m[:,:3],m[:,3]))
                self.stop.wait(.008)
            except Exception as e:
                logging.getLogger(__name__).warning('SteamVR unavailable: %s %r',type(e).__name__,e)
                if initialized: openvr.shutdown(); initialized=False
                self.stop.wait(2)
        if initialized: openvr.shutdown()
    def pose_at(self,t):
        if self.static: return np.eye(3),self.origin.copy()
        with self.lock: history=list(self.history)
        if not history or abs(history[-1][0]-t)>.3: raise ValueError('no recent HMD pose; suppress world tracking')
        times=np.array([v[0] for v in history]); i=int(np.searchsorted(times,t))
        if i==0 or i==len(history):
            item=history[min(i,len(history)-1)]
            if abs(item[0]-t)>.035: raise ValueError('capture outside HMD history')
            return item[1],item[2]
        a,b=history[i-1],history[i]; f=(t-a[0])/(b[0]-a[0]); qa=Rotation.from_matrix(a[1]); qb=Rotation.from_matrix(b[1])
        rot=Rotation.from_rotvec((qb*qa.inv()).as_rotvec()*f)*qa
        return rot.as_matrix(),a[2]*(1-f)+b[2]*f
    def transform(self,p,q,t,side):
        r,h=self.pose_at(t); cr=r@self.mount
        grip=Rotation.from_euler('xyz',self.config['grip_rotation_deg'][str(side)],degrees=True)
        position=h+r@self.offset+cr@p
        head_relative=Rotation.from_matrix(self.mount)*Rotation.from_quat(q)*grip
        head_relative=correct_head_relative_yaw(head_relative,self.config.get('invert_yaw',False))
        orientation=Rotation.from_matrix(r)*head_relative
        return position,orientation.as_quat()
    def close(self):
        self.stop.set()
        if not self.static and hasattr(self,'thread'): self.thread.join(3)
