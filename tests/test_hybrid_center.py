import json
from pathlib import Path
import numpy as np
import pytest,yaml
from scipy.spatial.transform import Rotation
from pc.glassvr.space import Space
from pc.tracking.filter import PoseFilter
from pc.controller.xinput import Mapper,Input

def config():return yaml.safe_load(Path('pc/config.yaml').read_text())['space']

def test_center_both_hands_matches_hmd_and_preserves_positions(tmp_path):
    path=tmp_path/'vision-hybrid-centering.json';space=Space(config(),path)
    hand_position=np.array([.1,-.15,.5]);original={s:q.as_quat().copy() for s,q in space.grip.items()}
    # Keep updating while held; changes in the user's grasp must be incorporated.
    for frame in range(4):
        t=10+frame/30;head=Rotation.from_euler('xyz',[.3+frame*.02,-.7,.2]);space.history.append((t,head.as_matrix(),np.array([1.,2.,3.])))
        for side in (1,2):
            hand=Rotation.from_euler('xyz',[side*.2+frame*.1,.6,-.3])
            before,_=space.transform(hand_position,hand.as_quat(),t,side)
            space.center_orientation(hand.as_quat(),t,side)
            after,q=space.transform(hand_position,hand.as_quat(),t,side)
            np.testing.assert_allclose(before,after,atol=1e-12)
            aim=Rotation.from_quat(q)*space.aim_tip[side]
            np.testing.assert_allclose(aim.as_matrix(),head.as_matrix(),atol=1e-12)
            np.testing.assert_allclose(aim.apply([0,0,-1]),head.apply([0,0,-1]),atol=1e-12)
    assert not path.exists() # No disk writes on every camera frame.
    assert space.save_centering() and not space.save_centering()
    data=json.loads(path.read_text());assert data['measured_sides']==[1,2]
    loaded=Space(config(),path)
    for side,name in ((1,'left'),(2,'right')):
        np.testing.assert_allclose(loaded.grip[side].as_matrix(),space.grip[side].as_matrix(),atol=1e-12)
        assert not np.allclose(data['hands'][name],original[side])
    assert not path.with_name(path.name+'.tmp').exists()

def test_missing_hand_does_not_acquire_a_fake_measurement(tmp_path):
    space=Space(config(),tmp_path/'vision-hybrid-centering.json');space.static=True
    left=space.grip[1].as_quat().copy();space.center_orientation([0,0,0,1],1,2);space.save_centering()
    data=json.loads(space.calibration_path.read_text());assert data['measured_sides']==[2]
    np.testing.assert_allclose(space.grip[1].as_quat(),left)

def test_bad_file_or_stale_hmd_never_overwrites_good_grip(tmp_path):
    path=tmp_path/'vision-hybrid-centering.json';path.write_text('{broken')
    space=Space(config(),path);before=space.grip[2].as_matrix().copy()
    with pytest.raises(ValueError):space.center_orientation([0,0,0,1],1,2)
    assert not space.center_dirty and path.read_text()=='{broken'
    np.testing.assert_allclose(space.grip[2].as_matrix(),before)

def test_disconnect_releases_centering_and_consumed_system_buttons():
    m=Mapper({'layout':'dual','left_trigger':'lt','right_trigger':'rt','left_grip':'lb','right_grip':'rb','left_menu':'x','right_menu':'y','left_system':'back','right_system':'start','left_stick_click':'ls','right_stick_click':'rs'})
    assert m.update(Input(True,{'start','back'}))[1]==['center_start']
    assert m.update(Input())[1]==['center_stop']
    assert m.update(Input(True,{'back'}))[0][1]['system']

def test_runtime_tip_metadata_and_saved_calibration_preserve_actual_forward_ray(tmp_path):
    path=tmp_path/'center.json';space=Space(config(),path);space.static=True
    custom={1:Rotation.from_euler('xyz',[-.6,-.12,.04]),2:Rotation.from_euler('xyz',[-.75,.09,-.03])}
    palm=Rotation.from_euler('xyz',[.7,-1.2,.4]).as_quat()
    for side in (1,2):space.center_orientation(palm,10,side)
    space.update_aim(custom)
    for side in (1,2):
        _,q=space.transform(np.array([.1,0,.5]),palm,10,side)
        np.testing.assert_allclose((Rotation.from_quat(q)*custom[side]).as_matrix(),np.eye(3),atol=1e-12)
    space.save_centering();loaded=Space(config(),path);loaded.static=True
    for side in (1,2):
        _,q=loaded.transform(np.array([.1,0,.5]),palm,10,side)
        np.testing.assert_allclose((Rotation.from_quat(q)*loaded.aim_tip[side]).apply([0,0,-1]),[0,0,-1],atol=1e-12)
    loaded.update_aim(custom)
    for side in (1,2):np.testing.assert_allclose(loaded.grip[side].as_matrix(),space.grip[side].as_matrix(),atol=1e-12)

def test_old_body_centering_is_not_loaded_as_tip_centering(tmp_path):
    path=tmp_path/'center.json';path.write_text(json.dumps({'format':1,'backend':'VisionHybrid','quaternion_order':'xyzw','hands':{'left':[0,0,0,1],'right':[0,0,0,1]}}))
    space=Space(config(),path)
    assert not space.centered_sides

def test_runtime_tip_reload_does_not_change_uncalibrated_hand_default(tmp_path):
    space=Space(config(),tmp_path/'center.json');space.static=True
    space.update_aim({1:Rotation.from_euler('xyz',[-.6,-.1,.07]),2:Rotation.from_euler('xyz',[-.7,.1,-.04])})
    left=space.grip[1].as_matrix().copy()
    space.center_orientation([0,0,0,1],10,2);space.save_centering()
    loaded=Space(config(),space.calibration_path)
    assert loaded.centered_sides=={2}
    np.testing.assert_allclose(loaded.grip[1].as_matrix(),left,atol=1e-12)

def test_runtime_tip_reads_tracking_to_component_local_without_starting_openvr():
    from pc.glassvr.aim import runtime_tips
    from types import SimpleNamespace
    expected=Rotation.from_euler('xyz',[-.7,.08,.02])
    matrix=np.column_stack((expected.as_matrix(),[.006,-.015,.02]))
    class Models:
        def getComponentState(self,name,component,controller,mode):
            assert component=='tip' and name.startswith('{indexcontroller}')
            return True,SimpleNamespace(mTrackingToComponentLocal=SimpleNamespace(m=matrix))
    fake=SimpleNamespace(VRRenderModels=Models,VRControllerState_t=object,RenderModel_ControllerMode_State_t=object)
    values=runtime_tips(fake)
    assert set(values)=={1,2}
    for value in values.values():np.testing.assert_allclose(value.as_matrix(),expected.as_matrix(),atol=1e-12)

def test_rotation_reset_preserves_filter_position_and_velocity():
    f=PoseFilter();f.update([0,0,1],[0,0,0,1],1);f.update([.01,0,1],[0,0,0,1],1.03)
    p=f.p.copy();v=f.velocity.copy();t=f.t;q=Rotation.from_euler('xyz',[.4,.5,.6]).as_quat()
    f.reset_rotation(q);np.testing.assert_allclose(f.q,q)
    np.testing.assert_array_equal(f.p,p);np.testing.assert_array_equal(f.velocity,v);assert f.t==t
