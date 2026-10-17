"""Native macOS CPU inference parity; not an iPhone/ANE speed benchmark."""
import importlib.util,itertools,json,plistlib,shutil,subprocess,tempfile
from pathlib import Path
import cv2,numpy as np,coremltools as ct

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference',root/'ios/assets/reference/pipeline.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
class Backend:
    def __init__(self,name):
        self.model=ct.models.MLModel(str(root/'ios/assets'/f'{name}.mlpackage'),compute_units=ct.ComputeUnit.CPU_ONLY)
        self.names=[o.name for o in self.model.get_spec().description.output]
    def __call__(self,x):
        values=self.model.predict({'image':x});return [values[n] for n in self.names]

cli=root/'ios/build/coreml_image_test'
subprocess.run(['clang++','-std=c++17','-O2','-ffp-contract=off','-fobjc-arc','-fblocks',str(root/'tests/coreml_image.mm'),str(root/'ios/Tracking/CoreMLTracker.mm'),'-framework','Foundation','-framework','CoreML','-framework','CoreVideo','-o',str(cli)],check=True)
with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp);bundle=temp/'Models.bundle';bundle.mkdir()
    (bundle/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'test.coreml.models','CFBundlePackageType':'BNDL'}))
    for name in ('hand_detector','hand_landmarks_detector'):shutil.copytree(root/'ios/build/host'/f'{name}.mlmodelc',bundle/f'{name}.mlmodelc')
    photo=cv2.imread(str(root/'ios/assets/reference/armandhand.JPG'));assert photo is not None
    rgb=cv2.cvtColor(cv2.resize(photo,(640,480)),cv2.COLOR_BGR2RGB)
    detector,landmark=Backend('hand_detector'),Backend('hand_landmarks_detector')
    report=[]
    for label,image in [('original',rgb),('mirrored',np.ascontiguousarray(rgb[:,::-1])),('two_hands',np.concatenate([cv2.resize(rgb,(320,480)),cv2.resize(rgb[:,::-1],(320,480))],axis=1))]:
        file=temp/'frame.bgra';file.write_bytes(cv2.cvtColor(image,cv2.COLOR_RGB2BGRA).tobytes())
        native=json.loads(subprocess.check_output([str(cli),str(bundle),str(file),'640','480'],text=True))
        pipeline=ref.HandLandmarker(detector,landmark,num_hands=2,fast_crop=True)
        for frame,hands in enumerate(native):
            reference=pipeline.detect_video(image);assert len(hands)==len(reference)>0,(label,frame,len(hands),len(reference))
            permutations=list(itertools.permutations(range(len(reference))))
            mapping=min(permutations,key=lambda ids:sum(np.linalg.norm(np.array(hands[i]['landmarks'])[0,:2]-reference[j]['landmarks'][0,:2]) for i,j in enumerate(ids)))
            for i,j in enumerate(mapping):
                h,r=hands[i],reference[j];uv=np.abs(np.array(h['landmarks'])[:,:2]-r['landmarks'][:,:2]);world=np.abs(np.array(h['world'])-r['world_landmarks'])
                assert h['side']==(2 if r['handedness']=='Right' else 1)
                assert uv.mean()<.01 and uv.max()<.03 and world.mean()<.005,(label,frame,float(uv.mean()),float(uv.max()),float(world.mean()))
                report.append({'image':label,'frame':frame,'hands':len(hands),'uv_mean':float(uv.mean()),'uv_max':float(uv.max()),'world_mean_m':float(world.mean())})
    print(json.dumps({'native_coreml_parity':'PASS','compute':'macOS CPU_ONLY, not iPhone/ANE','cases':report},indent=2))
