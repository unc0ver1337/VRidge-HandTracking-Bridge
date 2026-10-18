import cv2
import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from pc.protocol import Hand, Frame, encode, decode
from pc.tracking.hybrid import Decoder, PALM, IDS
from tests.geometry import Model

def sample(side=2, degrees=(15,25,10), capture=10., noise=0.):
    rotation=Rotation.from_euler('xyz',degrees,degrees=True)
    obj=PALM.copy()*(.085/np.linalg.norm(PALM[1]-PALM[4]))
    if side==1:obj[:,0]*=-1
    position=np.array([.04,-.03,.55]);k=np.array([420,418,320,240.])
    xyz=rotation.apply(obj)+position
    xy=xyz[:,:2]/xyz[:,2,None]*k[:2]+k[2:]
    xy+=np.random.default_rng(4).normal(0,noise,xy.shape)
    points=np.tile([.5,.5,1.],(21,1));points[IDS,:2]=xy/[640,480]
    world=Model().local(np.zeros((5,4)),side)
    hand=Hand(side,side,0,points,world,np.zeros(3),np.array([0,0,0,1.]),0,False,capture)
    return Frame(1,3,capture,640,480,k,[hand],2),rotation,position

@pytest.mark.parametrize('side',[1,2])
@pytest.mark.parametrize('degrees',[(15,25,10),(-40,-30,80),(145,20,-25),(10,65,20)])
def test_vision_recovers_known_palm_pose_both_sides(side,degrees):
    f,r,p=sample(side,degrees)
    out=Decoder().decode(f.hands[0],side,f)
    np.testing.assert_allclose(out.position,p,atol=1e-5)
    assert (Rotation.from_quat(out.quaternion)*r.inv()).magnitude()<1e-4
    assert np.count_nonzero(out.finger_valid)==5

def test_finger_deformation_cannot_move_or_rotate_controller():
    f,_,_=sample();a=Decoder().decode(f.hands[0],2,f)
    f.hands[0].world=Model().local(np.tile([.2,1.,1.,.8],(5,1)),2)
    f.hands[0].points[[4,8,12,16,20],:2]=.01
    b=Decoder().decode(f.hands[0],2,f)
    np.testing.assert_allclose(a.position,b.position)
    np.testing.assert_allclose(a.quaternion,b.quaternion)
    assert np.linalg.norm(a.angles-b.angles)>1

def test_missing_neural_fingers_preserves_vision_pose_and_ttl():
    f,_,_=sample();f.hands[0].finger_capture=f.capture-.4
    out=Decoder().decode(f.hands[0],2,f)
    assert not out.finger_valid.any()
    assert out.position[2]>.1
    f.hands[0].finger_capture=0;f.hands[0].world=np.zeros((21,3))
    assert not Decoder().decode(f.hands[0],2,f).finger_valid.any()

def test_continuous_turn_does_not_flip_quaternion_and_has_bounded_noise():
    solver=Decoder();last=None
    for i in range(60):
        f,_,p=sample(degrees=(20,15+i*.7,10),capture=10+i/30,noise=.3)
        out=solver.decode(f.hands[0],2,f)
        assert np.linalg.norm(out.position-p)<.025
        if last is not None:assert np.dot(last,out.quaternion)>0.95
        last=out.quaternion

def test_loss_rejects_low_confidence_and_new_stream_does_not_reuse_old_pose():
    f,_,_=sample();solver=Decoder();solver.decode(f.hands[0],2,f)
    f.hands[0].points[5,2]=0
    with pytest.raises(ValueError,match='occluded'):solver.decode(f.hands[0],2,f)
    f,_,_=sample(capture=20.,degrees=(145,20,-25))
    out=solver.decode(f.hands[0],2,f)
    assert np.isfinite(out.quaternion).all()

def test_protocol_independent_finger_timestamp_and_old_client_rejected():
    f,_,_=sample();f.hands[0].finger_capture=9.9
    raw=encode(f);out=decode(raw)
    assert out.flags==2 and out.hands[0].finger_capture==9.9
    old=bytearray(raw);old[4]=2
    with pytest.raises(ValueError,match='protocol'):decode(old)
    f.hands[0].finger_capture=11
    with pytest.raises(ValueError,match='timestamp'):encode(f)
