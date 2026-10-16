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

def test_center_actual_tip_instead_of_controller_body():
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text())['space'];s=Space(cfg)
    head=Rotation.from_euler('xyz',[.2,.7,-.1]);s.history.append((10,head.as_matrix(),np.zeros(3)))
    s.tip[2]=Rotation.from_euler('xyz',[-.7,.08,0])
    for a in ([.2,.3,.4],[.7,-.4,.1]):
        palm=Rotation.from_euler('xyz',a);s.center_orientation(palm.as_quat(),2)
        _,q=s.transform(np.array([0,0,.4]),palm.as_quat(),10,2)
        ray=Rotation.from_quat(q)*s.tip[2]
        np.testing.assert_allclose(ray.apply([0,0,-1]),head.apply([0,0,-1]),atol=1e-12)

def test_driver_and_bridge_tracking_key_contract():
    patch=Path('patches/glassvr-stable-controller-connection.patch').read_text()
    assert 'GetBoolFromSettingsByKey("tracking " + device)' in patch
    assert 'device + " tracking"' not in patch
