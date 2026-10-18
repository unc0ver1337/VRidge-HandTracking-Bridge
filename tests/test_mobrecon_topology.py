import json,hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]


def test_mesh_upsampling_and_spiral_topology():
    file=ROOT/'models/topology.npz';meta=json.loads((ROOT/'models/upstream.json').read_text())
    assert hashlib.sha256(file.read_bytes()).hexdigest()==meta['topology_sha256']
    t=np.load(file,allow_pickle=False)
    for i,shape in enumerate(((778,389),(389,195),(195,98),(98,49))):
        row,col,val=(t[k+str(i)] for k in ('up_row','up_col','up_val'))
        assert tuple(t['up_shape'+str(i)])==shape
        assert row.min()>=0 and row.max()<shape[0] and col.min()>=0 and col.max()<shape[1]
        # Preserve the author's coefficients verbatim. Some source rows are
        # not exactly barycentric; normalizing would change the trained model.
        assert np.isfinite(val).all()
        assert (np.bincount(row,minlength=shape[0])==3).all()
        spiral=t['spiral'+str(i)];assert spiral.shape==(shape[0],9)
        assert spiral.min()>=0 and spiral.max()<shape[0]


def test_joint_order_is_wrist_thumb_index_middle_ring_little():
    j=np.load(ROOT/'models/topology.npz')['j_reg_mpii'];assert j.shape==(21,778)
    np.testing.assert_allclose(j.sum(axis=1),1.,atol=1e-5)
    for joint,vertex in ((4,744),(8,333),(12,444),(16,555),(20,672)):
        assert np.count_nonzero(j[joint])==1 and j[joint,vertex]==1


def test_upstream_sources_are_pinned_with_only_equivalent_clip_cast():
    meta=json.loads((ROOT/'models/upstream.json').read_text())
    for name,sha in meta['sources'].items():
        data=(ROOT/'vendor/handmesh'/name).read_bytes().replace(b'\r\n',b'\n')
        if name=='mobrecon/models/modules.py':
            data=data.replace(b'torch.clamp((uv - 0.5) * 2, -1.0, 1.0)',b'torch.clamp((uv - 0.5) * 2, -1, 1)')
        assert hashlib.sha256(data).hexdigest()==sha,name
