import json
import numpy as np,yaml
from pathlib import Path
from scipy.spatial.transform import Rotation
from pc.glassvr.visibility import DevicePresence
from pc.glassvr.space import Space

def test_devices_stay_connected_tracking_validity_changes_per_hand(tmp_path):
    p=tmp_path/'settings.json';p.write_text(json.dumps({'enable cl':False,'enable cr':False,'untouched':123}))
    v=DevicePresence(p);v.flush();d=json.loads(p.read_text());assert d['enable cl'] and d['enable cr'] and not d['tracking cl'] and not d['tracking cr']
    v.update({1:True,2:False});v.flush();d=json.loads(p.read_text());assert d['enable cl'] and d['enable cr'] and d['tracking cl'] and not d['tracking cr'] and d['untouched']==123
    v.update({1:False,2:True});v.flush();d=json.loads(p.read_text());assert d['enable cl'] and d['enable cr'] and not d['tracking cl'] and d['tracking cr']
    v.close();d=json.loads(p.read_text());assert d['enable cl'] and d['enable cr'] and not d['tracking cr']

def test_saved_default_offsets_survive_relaunch_without_centering_api():
    from pc.glassvr.grip import DEFAULT_GRIP_XYZW
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text())['space']
    first,second=Space(cfg),Space(cfg)
    assert hasattr(first,'center_orientation') and not hasattr(first,'session_grip')
    assert not hasattr(first,'tip')
    for side in (1,2):
        np.testing.assert_allclose(first.grip[side].as_quat(),DEFAULT_GRIP_XYZW[side],atol=1e-15)
        np.testing.assert_allclose(first.grip[side].as_matrix(),second.grip[side].as_matrix(),atol=1e-15)
        assert abs(np.linalg.norm(DEFAULT_GRIP_XYZW[side])-1)<1e-12
    assert not np.allclose(first.grip[1].as_matrix(),first.grip[2].as_matrix())


def test_driver_and_bridge_tracking_key_contract():
    patch=Path('patches/glassvr-stable-controller-connection.patch').read_text()
    assert 'GetBoolFromSettingsByKey("tracking " + device)' in patch
    assert 'device + " tracking"' not in patch
