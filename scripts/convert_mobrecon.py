"""Export the official MobRecon SpConv checkpoint, with measured Core ML parity."""
import sys,json,hashlib
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import torch
import coremltools as ct
import cv2
import gdown

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vendor/handmesh'))
from cmr.models.mobrecon_densestack import MobRecon
import mobrecon.models.modules as layers


def main():
    torch.set_num_threads(2);torch.manual_seed(0)
    meta=json.loads((ROOT/'models/upstream.json').read_text())
    if hashlib.sha256((ROOT/'models/topology.npz').read_bytes()).hexdigest()!=meta['topology_sha256']:
        raise ValueError('topology SHA256 mismatch')
    assets=ROOT/'ios/assets';assets.mkdir(exist_ok=True,parents=True)
    checkpoint=assets/'mobrecon_densestack.pt'
    if not checkpoint.exists():
        gdown.download(id=meta['checkpoint_drive_id'],output=str(checkpoint),quiet=False,use_cookies=False)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=meta['checkpoint_sha256']:
        raise ValueError('checkpoint SHA256 mismatch')
    topo=np.load(ROOT/'models/topology.npz',allow_pickle=False)
    spirals=[torch.from_numpy(topo['spiral'+str(i)]) for i in range(4)]
    up=[tuple(torch.from_numpy(topo[key+str(i)]) for key in ('up_row','up_col','up_val')) for i in range(4)]
    model=MobRecon(SimpleNamespace(out_channels=[32,64,128,256],dsconv=False),spirals,up).eval()
    state=torch.load(checkpoint,map_location='cpu',weights_only=True)
    if 'model_state_dict' in state:state=state['model_state_dict']
    model.load_state_dict(state,strict=True)
    model.requires_grad_(False)
    # Core ML clip expects floating bounds for floating activations. Casting
    # these exact integers to float changes no values or trained weights.
    for block in model.modules():
        if isinstance(block,torch.nn.Hardtanh):
            block.min_val=float(block.min_val);block.max_val=float(block.max_val)
    samples=[]
    for p in sorted((ROOT/'tests/images').glob('*.jpg')):
        rgb=cv2.cvtColor(cv2.imread(str(p)),cv2.COLOR_BGR2RGB)
        for flip in (False,True):
            image=rgb[:,::-1] if flip else rgb
            x=(cv2.resize(image,(128,128)).astype(np.float32)/255-.5)/.5
            samples.append((p.stem+('_mirror' if flip else ''),torch.from_numpy(x.transpose(2,0,1).copy())[None]))
    if not samples:raise ValueError('real test images required')
    with torch.inference_mode():reference=[model(x) for _,x in samples]
    # Replace sparse scatter-add pooling with mathematically equivalent constant
    # dense matmul. This avoids unsupported Core ML scatter operators.
    dense=[]
    for i,(row,col,value) in enumerate(up):
        shape=tuple(topo['up_shape'+str(i)].tolist())
        dense.append(torch.sparse_coo_tensor(torch.stack((row,col)),value,shape).to_dense())
    layers.Pool=lambda x,trans,dim=1:torch.matmul(trans,x)
    model.decoder3d.up_transform=dense
    with torch.inference_mode():
        for (_,x),ref in zip(samples,reference):
            out=model(x)
            torch.testing.assert_close(out['mesh_pred'],ref['mesh_pred'],atol=2e-5,rtol=2e-4)
            torch.testing.assert_close(out['uv_pred'],ref['uv_pred'],atol=1e-6,rtol=1e-5)

    class Export(torch.nn.Module):
        def __init__(self):
            super().__init__();self.model=model
            self.register_buffer('regressor',torch.from_numpy(topo['j_reg_mpii']))
        def forward(self,image):
            out=self.model(image)
            joints=torch.matmul(self.regressor,out['mesh_pred'])*.20
            return joints-joints[:,:1],out['uv_pred']

    export=Export().eval();example=samples[0][1]
    traced=torch.jit.trace(export,example,strict=True)
    ml=ct.convert(traced,inputs=[ct.TensorType(name='image',shape=(1,3,128,128),dtype=np.float32)],
                  outputs=[ct.TensorType(name='joints',dtype=np.float32),ct.TensorType(name='landmarks2d',dtype=np.float32)],
                  minimum_deployment_target=ct.target.iOS16,convert_to='mlprogram',
                  compute_precision=ct.precision.FLOAT32)
    ml.short_description='Official MobRecon DenseStack SpConv; wrist-relative MPII joints in metres'
    ml.author='Xingyu Chen et al.; experimental Core ML integration by unc0ver1337'
    ml.user_defined_metadata['checkpoint_sha256']=meta['checkpoint_sha256']
    ml.save(str(assets/'mobrecon.mlpackage'))
    cpu=ct.models.MLModel(str(assets/'mobrecon.mlpackage'),compute_units=ct.ComputeUnit.CPU_ONLY)
    records=[]
    with torch.inference_mode():
        for name,x in samples:
            expected=export(x);actual=cpu.predict({'image':x.numpy()})
            jerr=np.abs(actual['joints']-expected[0].numpy());uerr=np.abs(actual['landmarks2d']-expected[1].numpy())
            if jerr.max()>.005 or jerr.mean()>.001 or uerr.max()>.01:
                raise ValueError(f'Core ML parity failed: {name} joints={jerr.max()} uv={uerr.max()}')
            records.append({'sample':name,'joint_mean_m':float(jerr.mean()),'joint_max_m':float(jerr.max()),'uv_max':float(uerr.max())})
    report={'model':'MobRecon DenseStack SpConv (official 2023 demo)','checkpoint_sha256':meta['checkpoint_sha256'],
            'upstream_commit':meta['commit'],'precision':'FLOAT32 (FP16 failed output parity)',
            'compute':'macOS CPU_ONLY, not iPhone speed/accuracy','cases':records,'parity':'PASS'}
    (assets/'mobrecon-parity.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
