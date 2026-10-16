import numpy as np,pytest
from scipy.spatial.transform import Rotation
from pc.protocol import Frame,Hand
from pc.reconstruction.model import Model,project,rays
from pc.reconstruction.solver import Solver
from pc.reconstruction.calibration import rigid_alignment

K=np.array([420,420,320,240])
def synthetic(side=2,depth=.55,rotation=(np.pi,0,0),flex=.1):
    model=Model();x=np.r_[[0,0,depth],rotation,np.tile([0,flex,flex,flex*.65],5)]
    joints=model.forward(x,side);uv=project(joints,K)
    hand=Hand(side,side,0,np.column_stack([uv/[640,480],np.ones(21)]))
    return x,joints,hand,Frame(1,1,1,640,480,K,[hand])

@pytest.mark.parametrize('side',[1,2])
@pytest.mark.parametrize('depth',[.35,.55,.85])
def test_synthetic_metric_reconstruction(side,depth):
    x,joints,h,f=synthetic(side,depth);s=Solver(max_evaluations=60);out=s.solve(h,f,side)
    assert out.pixel_rmse<3
    assert abs(out.position[2]-depth)<.08
    assert abs(np.linalg.norm(out.quaternion)-1)<1e-8
    assert out.orientation_ambiguous and out.depth_sigma_m>0

@pytest.mark.parametrize('rot',[(2.5,.3,.4),(.4,2.5,.2),(0,0,.4)])
def test_rotated_palm_reprojection(rot):
    x,j,h,f=synthetic(rotation=rot);o=Solver(max_evaluations=70).solve(h,f,2)
    assert o.pixel_rmse<8 # Reprojection evidence, not proof of unique orientation.

def test_bone_lengths_exact_under_flex():
    m=Model();j=m.forward(np.r_[[0,0,.6],[.2,.3,.1],np.tile([.2,.5,.8,.5],5)],1)
    for i in range(5):
        np.testing.assert_allclose(np.linalg.norm(np.diff(j[1+4*i:5+4*i],axis=0),axis=1),m.lengths[i],atol=1e-12)

def test_vectorized_model_matches_scalar():
    rng=np.random.default_rng(13);m=Model();x=rng.normal(0,.3,(52,26));x[:,2]+=.7
    for side in (1,2):
        np.testing.assert_allclose(m.forward_batch(x,side),np.array([m.forward(a,side) for a in x]),atol=1e-12)

def test_lens_roundtrip():
    uv=np.array([[100,120],[320,240],[580,420]],float);d=[-.12,.03,.001,-.002,0]
    rr=rays(uv,K,d);np.testing.assert_allclose(project(rr,K,d),uv,atol=1e-4)

def test_occlusion_reject():
    _,_,h,f=synthetic();h.points[:,2]=0
    with pytest.raises(ValueError): Solver().solve(h,f,2)

def test_partial_finger_occlusion_uses_bounded_kinematics():
    _,_,h,f=synthetic(flex=.25);s=Solver();s.solve(h,f,2)
    f.capture+=1/30;h.points[[6,7,10,11,14,15],2]=0
    out=s.solve(h,f,2)
    assert out.pixel_rmse<5 and np.isfinite(out.joints).all()
    assert np.ptp(out.joints[:,2])>.005 # nonconstant per-landmark depth

def test_rigid_calibration():
    a=np.array([[0,0,0],[1,0,0],[0,1,0],[0,0,1]],float);r=Rotation.from_euler('xyz',[.2,.3,.4]).as_matrix();t=np.array([.1,.2,.3]);b=a@r.T+t
    rr,tt,error=rigid_alignment(a,b);np.testing.assert_allclose(rr,r,atol=1e-12);np.testing.assert_allclose(tt,t);assert error<1e-10
    with pytest.raises(ValueError):rigid_alignment(a[:2],b[:2])

@pytest.mark.parametrize('side',[1,2])
def test_finger_motion_does_not_change_rigid_palm_pose(side):
    _,_,hand,frame=synthetic(side=side,flex=.1)
    sa=Solver(max_evaluations=50);sb=Solver(max_evaluations=50)
    sa.solve(hand,frame,side);sb.solve(hand,frame,side)
    frame.capture+=1/30
    a=sa.solve(hand,frame,side)
    _,_,changed,other=synthetic(side=side,flex=.6);other.capture=frame.capture
    b=sb.solve(changed,other,side)
    np.testing.assert_allclose(a.position,b.position,atol=1e-10)
    np.testing.assert_allclose(a.quaternion,b.quaternion,atol=1e-10)

def test_invalid_coordinates_rejected_before_optimization():
    _,_,hand,frame=synthetic();hand.points[8,0]=np.nan
    with pytest.raises(ValueError):Solver().solve(hand,frame,2)

@pytest.mark.parametrize('side',[1,2])
def test_bad_fingertips_do_not_remove_good_palm(side):
    _,_,h,f=synthetic(side=side);solver=Solver();old=solver.solve(h,f,side)
    f.capture+=1/30;h.points[6:9,:2]+=.3
    out=solver.solve(h,f,side)
    assert out.palm_rmse<3 and not out.finger_valid[1]
    np.testing.assert_allclose(out.angles[1],old.angles[1])
