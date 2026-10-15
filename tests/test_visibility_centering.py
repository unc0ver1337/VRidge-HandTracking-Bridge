import json
import numpy as np,yaml
from pathlib import Path
from scipy.spatial.transform import Rotation
from pc.glassvr.visibility import Visibility
from pc.glassvr.space import Space

def test_visibility_each_hand_loss_recovery_and_shutdown(tmp_path):
    p=tmp_path/'settings.json';p.write_text(json.dumps({'enable cl':True,'enable cr':True,'untouched':123}))
    v=Visibility(p);v.flush();d=json.loads(p.read_text());assert not d['enable cl'] and not d['enable cr']
    v.update({1:True,2:False});v.flush();d=json.loads(p.read_text());assert d['enable cl'] and not d['enable cr'] and d['untouched']==123
    v.update({1:False,2:True});v.flush();d=json.loads(p.read_text());assert not d['enable cl'] and d['enable cr']
    v.close();assert not json.loads(p.read_text())['enable cr']

def test_center_actual_tip_instead_of_controller_body():
    cfg=yaml.safe_load(Path('pc/config.yaml').read_text())['space'];s=Space(cfg)
    head=Rotation.from_euler('xyz',[.2,.7,-.1]);s.history.append((10,head.as_matrix(),np.zeros(3)))
    s.tip[2]=Rotation.from_euler('xyz',[-.7,.08,0])
    for a in ([.2,.3,.4],[.7,-.4,.1]):
        palm=Rotation.from_euler('xyz',a);s.center_orientation(palm.as_quat(),2)
        _,q=s.transform(np.array([0,0,.4]),palm.as_quat(),10,2)
        ray=Rotation.from_quat(q)*s.tip[2]
        np.testing.assert_allclose(ray.apply([0,0,-1]),head.apply([0,0,-1]),atol=1e-12)
