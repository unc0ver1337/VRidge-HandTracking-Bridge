import struct,socket
from pathlib import Path
import numpy as np,yaml
from scipy.spatial.transform import Rotation
from pc.tracking.identity import Identity
from pc.tracking.filter import PoseFilter
from pc.protocol import Hand
from pc.controller.xinput import Mapper,Input,deadzone,XInput
from pc.glassvr.adapter import packets,GlassVR
from pc.glassvr.space import Space

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
