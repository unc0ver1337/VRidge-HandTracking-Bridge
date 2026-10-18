import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from pc.protocol import Hand,Frame,encode,decode
from tests.geometry import Model
from pc.tracking.mediapipe import Decoder

@pytest.mark.parametrize('side',[1,2])
def test_phone_geometry_is_used_without_pc_ik(side):
    m=Model();world=m.local(np.tile([0,.3,.4,.2],(5,1)),side);p=np.array([.05,-.03,.6]);q=np.array([0,0,0,1.])
    h=Hand(side,side,0,np.full((21,3),.5),world,p,q,2.,True)
    f=Frame(1,1,1,640,480,np.array([400,400,320,240]),[h]);g=decode(encode(f));out=Decoder().decode(g.hands[0],side)
    np.testing.assert_allclose(out.position,p,atol=1e-6);np.testing.assert_allclose(out.quaternion,q,atol=1e-6)
    assert out.angles.shape==(5,4) and np.isfinite(out.angles).all()
    g.hands[0].pose_valid=False
    with pytest.raises(ValueError):Decoder().decode(g.hands[0],side)

def test_baseline_packets_are_rejected():
    from pc.protocol import HEADER
    raw=HEADER.pack(b'VHBR',1,0,0,1,1,1.,640,480,400,400,320,240)
    with pytest.raises(ValueError):decode(raw)

@pytest.mark.parametrize('reported,assigned',[(1,2),(2,1),(0,1),(0,2)])
def test_semantic_role_correction_cancels_phone_basis_flip(reported,assigned):
    world=Model().local(np.tile([0,.3,.4,.2],(5,1)),assigned)
    canonical=Rotation.from_euler('xyz',[.2,.1,-.4])
    phone=canonical*Rotation.from_euler('y',180,degrees=True) if (reported==1)!=(assigned==1) else canonical
    p=np.array([0,0,.5]);world=canonical.apply(world)
    h=Hand(1,reported,0,np.full((21,3),.5),world,p,phone.as_quat(),1.,True)
    out=Decoder().decode(h,assigned)
    assert (Rotation.from_quat(out.quaternion)*canonical.inv()).magnitude()<1e-7
    np.testing.assert_allclose(out.joints,world-world[0]+p)

@pytest.mark.parametrize('field,value',[('quaternion',np.array([0,0,0,0])),('position',np.array([0,0,-.5])),('world',np.full((21,3),np.nan)),('reprojection',21.)])
def test_invalid_3d_packets_never_enter_decoder(field,value):
    h=Hand(1,2,0,np.full((21,3),.5),np.zeros((21,3)),np.array([0,0,.5]),np.array([0,0,0,1]),0.,True)
    setattr(h,field,value)
    f=Frame(1,1,1.,640,480,np.array([400,400,320,240]),[h])
    with pytest.raises(ValueError):encode(f)

def test_bad_finger_does_not_remove_valid_controller_pose():
    world=Model().local(np.tile([0,.3,.4,.2],(5,1)),2)
    world[6:9]=world[5] # Index finger has zero-length segments.
    h=Hand(1,2,0,np.full((21,3),.5),world,np.array([.1,0,.5]),np.array([0,0,0,1]),1.,True)
    out=Decoder().decode(h,2)
    np.testing.assert_array_equal(out.position,h.position)
    assert out.finger_valid.tolist()==[True,False,True,True,True]
    assert np.isfinite(out.angles).all()

def test_invalid_finger_hold_expires_using_last_valid_digit_time():
    from pc.glassvr.adapter import GlassVR
    class Sink:
        def sendto(self,data,dest):return len(data)
    g=GlassVR();g.sock.close();g.sock=Sink()
    pose=([0,0,.5],[0,0,0,1],{})
    a=np.full((5,4),.5);valid=np.array([True,False,True,True,True])
    g.send(2,*pose,a,sample_time=10)
    for step in range(1,7):
        g.send(2,*pose,np.zeros((5,4)),sample_time=10+step/30,finger_valid=valid)
    np.testing.assert_allclose(g.fingers[2][2][1],.5)
    for step in range(7,30):
        g.send(2,*pose,np.zeros((5,4)),sample_time=10+step/30,finger_valid=valid)
    assert np.max(g.fingers[2][2][1])<.001
    assert g.finger_seen[2][1]==10 and g.finger_seen[2][0]>10.9

@pytest.mark.parametrize('side',[1,2])
def test_direct_decoder_rejects_nonunit_orientation(side):
    h=Hand(1,side,0,np.full((21,3),.5),np.zeros((21,3)),np.array([0,0,.5]),np.array([0,0,0,2]),0.,True)
    with pytest.raises(ValueError,match='MP pose'):Decoder().decode(h,side)

def test_legacy_model_pose_decoder_is_not_used_by_hybrid_runtime():
    from pathlib import Path
    source=(Path(__file__).resolve().parents[1]/'pc/bridge.py').read_text(encoding='utf8')
    assert 'from .tracking.hybrid import Decoder' in source
