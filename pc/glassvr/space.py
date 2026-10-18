import threading,time,logging,json,os
from pathlib import Path
from collections import deque
import numpy as np
from scipy.spatial.transform import Rotation
from .grip import DEFAULT_GRIP_XYZW
from .aim import stock_tips,runtime_tips

class Space:
    """Timestamped HMD history + measured rigid camera mount. SteamVR metres.

    Camera: +X right,+Y down,+Z forward. OpenVR: +X right,+Y up,-Z forward.
    Camera mount translation is the camera centre expressed in HMD coordinates.
    Driver UDP poses are RAW tracking coordinates. SteamVR applies its room/standing
    transform afterwards; using Standing HMD samples here would apply it twice.
    """
    def __init__(self,config,calibration_path=None):
        self.config=config; self.history=deque(maxlen=300); self.stop=threading.Event(); self.lock=threading.Lock()
        self.mount=Rotation.from_euler('xyz',config['camera_rotation_deg'],degrees=True).as_matrix()@np.diag([1,-1,-1])
        self.offset=np.asarray(config['camera_offset_m'],float); self.static=config['mode']=='static'
        self.origin=np.array(config.get('static_origin_m',[0,1.6,0]),float)
        self.grip={side:Rotation.from_quat(q) for side,q in DEFAULT_GRIP_XYZW.items()}
        self.aim_tip=stock_tips()
        self.calibration_path=Path(calibration_path) if calibration_path else None
        self.centered_sides=set();self.center_dirty=False;self.center_holding=False
        self.load_centering()
    def load_centering(self):
        if not self.calibration_path or not self.calibration_path.exists():return
        try:
            data=json.loads(self.calibration_path.read_text(encoding='utf8'))
            if data.get('format')!=2 or data.get('target')!='index-tip-hmd-forward' or data.get('backend')!='VisionHybrid' or data.get('quaternion_order')!='xyzw':raise ValueError('old or unsupported centering file; hold Back+Start to recalibrate')
            loaded={}
            for side,name in ((1,'left'),(2,'right')):
                q=np.asarray(data['hands'][name],float)
                if q.shape!=(4,) or not np.isfinite(q).all() or np.linalg.norm(q)<1e-8:raise ValueError('invalid centering quaternion')
                tip=np.asarray(data['aim_local_xyzw'][name],float)
                if tip.shape!=(4,) or not np.isfinite(tip).all() or np.linalg.norm(tip)<1e-8:raise ValueError('invalid saved aim quaternion')
                loaded[side]=Rotation.from_quat(q)*Rotation.from_quat(tip)*self.aim_tip[side].inv()
            observed=set(data.get('measured_sides',[]))
            if not observed<={1,2}:raise ValueError('invalid measured sides')
            self.grip=loaded;self.centered_sides=observed
            logging.getLogger(__name__).info('Loaded VisionHybrid centering: %s',self.calibration_path)
        except (OSError,ValueError,KeyError,TypeError):logging.getLogger(__name__).exception('Ignoring invalid VisionHybrid centering; keeping defaults')
    def center_orientation(self,q,t,side):
        if side not in self.grip:raise ValueError('invalid hand side')
        hand=np.asarray(q,float)
        if hand.shape!=(4,) or not np.isfinite(hand).all() or np.linalg.norm(hand)<1e-8:raise ValueError('invalid hand orientation')
        r,_=self.pose_at(t)
        base=Rotation.from_matrix(r@self.mount)*Rotation.from_quat(hand)*Rotation.from_euler('x',90,degrees=True)
        # Match the actual INDEX TIP frame to the HMD, not the controller body.
        # (body_world * tip_local) must equal head_world; forward is -Z.
        with self.lock:
            tip=self.aim_tip[side]
            self.grip[side]=base.inv()*Rotation.from_matrix(r)*tip.inv()
        self.centered_sides.add(side);self.center_dirty=True
    def save_centering(self):
        if not self.center_dirty:return False
        data={'format':2,'target':'index-tip-hmd-forward','backend':'VisionHybrid','quaternion_order':'xyzw','measured_sides':sorted(self.centered_sides),
              'aim_local_xyzw':{name:self.aim_tip[side].as_quat().tolist() for side,name in ((1,'left'),(2,'right'))},
              'hands':{name:self.grip[side].as_quat().tolist() for side,name in ((1,'left'),(2,'right'))}}
        if self.calibration_path:
            temporary=self.calibration_path.with_name(self.calibration_path.name+'.tmp')
            try:
                with temporary.open('w',encoding='utf8') as stream:
                    json.dump(data,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,self.calibration_path)
            except OSError:
                temporary.unlink(missing_ok=True);raise
        logging.getLogger(__name__).info('VisionHybrid centering XYZW: %s; saved=%s',json.dumps(data['hands']),self.calibration_path)
        self.center_dirty=False;return True
    def start(self):
        if not self.static:
            self.thread=threading.Thread(target=self.poll,name='openvr',daemon=True); self.thread.start()
    def update_aim(self,tips):
        with self.lock:
            for side,tip in tips.items():
                if side not in (1,2):continue
                if (self.aim_tip[side]*tip.inv()).magnitude()<1e-8:continue
                if side in self.centered_sides:
                    self.grip[side]=self.grip[side]*self.aim_tip[side]*tip.inv()
                self.aim_tip[side]=tip
    def poll(self):
        import openvr
        initialized=False;aim_checked=0
        while not self.stop.is_set():
            try:
                if not initialized:
                    openvr.init(openvr.VRApplication_Background); initialized=True;aim_checked=0
                if time.monotonic()-aim_checked>5:
                    try:self.update_aim(runtime_tips(openvr))
                    except Exception as error:logging.getLogger(__name__).debug('Index tip metadata unavailable; using last known component: %s',error)
                    aim_checked=time.monotonic()
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
        grip=self.grip[side]
        position=h+r@self.offset+cr@p
        orientation=Rotation.from_matrix(cr)*Rotation.from_quat(q)*Rotation.from_euler('x',90,degrees=True)*grip
        return position,orientation.as_quat()
    def close(self):
        self.stop.set()
        if not self.static and hasattr(self,'thread'): self.thread.join(3)
        if self.center_dirty:
            try:self.save_centering()
            except OSError:logging.getLogger(__name__).exception('Could not save VisionHybrid centering')
