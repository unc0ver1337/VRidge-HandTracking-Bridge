import numpy as np
import pytest
from scipy.spatial.transform import Rotation
from tests.test_reconstruction import synthetic
import pc.reconstruction.solver as module

@pytest.mark.parametrize('side',[1,2])
@pytest.mark.parametrize('gap',[1/30,.4])
def test_spurious_half_turn_is_held_but_position_remains_measured(monkeypatch,side,gap):
    _,_,hand,frame=synthetic(side=side);solver=module.Solver(max_evaluations=50)
    first=solver.solve(hand,frame,side);original=module.least_squares
    def broken_palm(fun,x,*args,**kwargs):
        result=original(fun,x,*args,**kwargs)
        if len(x)==6:
            result.x[3:6]=(Rotation.from_quat(first.quaternion)*Rotation.from_rotvec([0,np.pi,0])).as_rotvec()
        return result
    monkeypatch.setattr(module,'least_squares',broken_palm)
    frame.capture+=gap;hand.points[:,0]+=.01
    out=solver.solve(hand,frame,side)
    assert out.orientation_held
    assert (Rotation.from_quat(out.quaternion)*Rotation.from_quat(first.quaternion).inv()).magnitude()<1e-6
    assert out.position[0]>first.position[0]

def test_smooth_true_turn_is_not_frozen():
    solver=module.Solver(max_evaluations=50)
    qs=[]
    for i in range(12):
        _,_,hand,frame=synthetic(rotation=(np.pi,.02*i,0));frame.capture=1+i/30
        out=solver.solve(hand,frame,2);qs.append(out.quaternion)
        assert not out.orientation_held
    assert (Rotation.from_quat(qs[-1])*Rotation.from_quat(qs[0]).inv()).magnitude()>.1
