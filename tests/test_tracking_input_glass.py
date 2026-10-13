import struct,socket
import time
from pathlib import Path
import numpy as np,yaml
from scipy.spatial.transform import Rotation
from pc.tracking.identity import Identity
from pc.tracking.filter import PoseFilter
from pc.protocol import Hand
from pc.controller.xinput import Mapper,Input,deadzone,XInput
from pc.controller.manager import InputManager
from pc.glassvr.adapter import packets,GlassVR
from pc.glassvr.space import Space,correct_head_relative_yaw

def hand(side,x):
    p=np.full((21,3),.8);p[:,0]=x;return Hand(side,side,0,p)

def test_identity_crossing_and_chirality_flicker():
    tracker=Identity();assert set(tracker.update([hand(1,.2),hand(2,.8)],0))=={1,2}
    tracker.update([hand(1,.4),hand(2,.6)],.1)
    out=tracker.update([hand(2,.58),hand(1,.42)],.2)
    assert out[1].points[0,0]==.58 and out[2].points[0,0]==.42

def test_disappear_and_reacquire():
    tr=Identity(); tr.update([hand(1,.3)],0);assert tr.update([],.1)=={}
    assert 1 in tr.update([hand(1,.32)],.3)
    assert tr.update([hand(1,.9)],1.2)[1].points[0,0]==.9

def test_filters_jitter_quaternion_sign_and_prediction():
    rng=np.random.default_rng(4);f=PoseFilter(prediction_ms=0);positions=[]
    for i in range(200):
        p,q=f.update(rng.normal(0,.003,3),np.array([0,0,0,(-1.)**i]),i/60)
        positions.append(p);assert abs(np.linalg.norm(q)-1)<1e-10
    assert np.std(np.array(positions)[30:])<.002
    p,q=f.update([.5,0,0],[0,0,1,0],4);assert np.isfinite(p).all()

def test_reacquisition_does_not_teleport():
    f=PoseFilter(prediction_ms=0);f.update([0,0,0],[0,0,0,1],0)
    p,q=f.update([1,0,0],[0,0,1,0],2)
    assert np.linalg.norm(p)<=.1+1e-9
    assert Rotation.from_quat(q).magnitude()<=.4+1e-9

def test_glassvr_splay_and_curl_units():
    angles=np.zeros((5,4));angles[1]=np.deg2rad([15,90,80,80]);raw=packets([0,0,0],[0,0,0,1],{},angles)[3]
    values=struct.unpack('<c25d',raw)[1:];assert abs(values[4]-1)<1e-9;assert abs(values[21]-1)<1e-9

def test_input_switch_disconnect_and_analog():
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text());m=Mapper(cfg['mapping'])
    out,e=m.update(Input(True,{'lb','a'},.4,.7,(.2,.5),(.3,.1)))
    assert out[1]['a'] and out[1]['trigger']==.7 and out[1]['grip_pull']==.4
    out,e=m.update(Input(True,{'rb','a'}));assert not out[1].get('a',False) and out[2]['a']
    out,e=m.update(Input());assert out=={1:{},2:{}}
    assert deadzone(.01,.02,.18)==(0,0)
    assert np.linalg.norm(deadzone(1,1,.18))<=1.000000001
    assert isinstance(XInput().poll(),Input)

def test_input_loop_releases_on_loss_without_camera_processing():
    class Sink:
        def __init__(self):self.latest={}
        def input_only(self,side,buttons):self.latest[side]=buttons.copy()
    class Pad:
        def poll(self):return Input(True,{'lb','a'})
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text());sink=Sink();m=InputManager(sink,cfg['xinput'],cfg['mapping']);m.pad=Pad()
    m.tracked(1,time.monotonic());m.start()
    try:
        end=time.monotonic()+1
        while not sink.latest.get(1,{}).get('a') and time.monotonic()<end:time.sleep(.01)
        assert sink.latest[1]['a']
        # Reconstruction is absent/blocked; the independent loop still releases.
        with m.lock:m.valid_until[1]=0
        end=time.monotonic()+1
        while sink.latest[1] and time.monotonic()<end:time.sleep(.01)
        assert sink.latest[1]=={}
    finally:m.close()

def test_glassvr_exact_upstream_wire_and_loopback():
    b=packets([.1,.2,.3],[0,0,0,1],{'a':True,'trigger':.6},np.zeros((5,4)))
    assert list(map(len,b))==[25,33,77,201]
    assert struct.unpack('<c4d',b[1])==(b'R',1,0,0,0)
    assert struct.unpack('<c12?8d',b[2])[1] is True
    assert struct.unpack('<c12?8d',b[2])[-4]==.6
    with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as rx:
        rx.bind(('127.0.0.1',0));rx.settimeout(1);port=rx.getsockname()[1]
        g=GlassVR(left_port=port,right_port=port);g.send(1,[.1,.2,.3],[0,0,0,1],{'a':True,'trigger':.6},np.zeros((5,4)))
        assert [rx.recv(512) for _ in range(4)]==b;g.close()

def test_camera_openvr_transform_and_hmd_interpolation():
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text())['space'];s=Space(cfg)
    s.history.extend([(10,np.eye(3),np.array([0,1,0])),(10.1,Rotation.from_euler('y',.2).as_matrix(),np.array([.1,1,0]))])
    r,p=s.pose_at(10.05);np.testing.assert_allclose(p,[.05,1,0]);np.testing.assert_allclose(Rotation.from_matrix(r).as_rotvec(),[0,.1,0],atol=1e-10)
    p,q=s.transform(np.array([0,0,.5]),[0,0,0,1],10,2);np.testing.assert_allclose(p,[0,1,-.5]);assert abs(np.linalg.norm(q)-1)<1e-10

def test_controllers_follow_hmd_forward_and_room_transform_applies_once():
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text())['space'];s=Space(cfg)
    head_r=Rotation.from_euler('y',.8).as_matrix();head_p=np.array([.2,1.4,-.3])
    s.history.append((10,head_r,head_p))
    hand_p,hand_q=s.transform(np.array([.1,.05,.5]),[0,0,0,1],10,2)
    # Relative to the headset: camera right is head right, camera down is head
    # down, camera forward is headset look direction (-Z), at every yaw.
    np.testing.assert_allclose(head_r.T@(hand_p-head_p),[.1,-.05,-.5],atol=1e-12)
    room_r=Rotation.from_euler('y',-.4).as_matrix();room_p=np.array([2,0,1])
    standing_head=room_r@head_p+room_p;standing_hand=room_r@hand_p+room_p
    np.testing.assert_allclose((room_r@head_r).T@(standing_hand-standing_head),[.1,-.05,-.5],atol=1e-12)

def test_yaw_inversion_keeps_pitch_roll_and_is_reversible():
    for yaw in (-1.1,-.4,0,.4,1.1):
        expected=np.array([-yaw,.3,-.2]);r=Rotation.from_euler('YXZ',[yaw,.3,-.2])
        corrected=correct_head_relative_yaw(r,True)
        np.testing.assert_allclose(corrected.as_euler('YXZ'),expected,atol=1e-12)
        np.testing.assert_allclose(correct_head_relative_yaw(corrected,True).as_matrix(),r.as_matrix(),atol=1e-12)
        np.testing.assert_allclose(correct_head_relative_yaw(r,False).as_matrix(),r.as_matrix())

def test_yaw_correction_does_not_change_positions_or_depend_on_room_heading():
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text())['space'];s=Space(cfg)
    head=Rotation.from_euler('xyz',[.2,1.2,-.1]);s.history.append((10,head.as_matrix(),np.array([1.,2.,3.])))
    desired=Rotation.from_euler('YXZ',[.6,.25,.1])
    palm=Rotation.from_matrix(s.mount).inv()*desired
    p0,q0=s.transform(np.array([.1,.05,.4]),palm.as_quat(),10,2)
    cfg['invert_yaw']=True
    p1,q1=s.transform(np.array([.1,.05,.4]),palm.as_quat(),10,2)
    np.testing.assert_allclose(p1,p0,atol=1e-12)
    relative=head.inv()*Rotation.from_quat(q1)
    np.testing.assert_allclose(relative.as_euler('YXZ'),[-.6,.25,.1],atol=1e-12)

def test_vertical_aim_stays_finite_without_changing_up_down():
    for pitch in (-np.pi/2,np.pi/2):
        r=Rotation.from_euler('YXZ',[1.,pitch,.2]);corrected=correct_head_relative_yaw(r,True)
        np.testing.assert_allclose(corrected.apply([0,0,-1]),r.apply([0,0,-1]),atol=1e-12)
        assert np.isfinite(corrected.as_quat()).all()
