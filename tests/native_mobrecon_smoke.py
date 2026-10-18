"""Real native Vision ROI + Core ML processing on macOS, not iPhone benchmark."""
from pathlib import Path
import subprocess,tempfile,plistlib,shutil,json
import numpy as np,cv2
root=Path(__file__).resolve().parents[1];cli=root/'ios/build/native_mobrecon'
subprocess.run(['clang++','-std=c++17','-O2','-fobjc-arc','-fblocks',str(root/'tests/coreml_image.mm'),str(root/'ios/Tracking/CoreMLTracker.mm'),
                '-framework','Foundation','-framework','CoreML','-framework','CoreVideo','-framework','Vision','-framework','ImageIO','-o',str(cli)],check=True)
reports=[]
with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp);bundle=temp/'MobRecon.bundle';bundle.mkdir()
    (bundle/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'test.mobrecon','CFBundlePackageType':'BNDL'}))
    shutil.copytree(root/'ios/build/host/mobrecon.mlmodelc',bundle/'mobrecon.mlmodelc')
    for p in sorted((root/'tests/images').glob('*.jpg')):
        photo=cv2.imread(str(p));assert photo is not None
        for mirror in (False,True):
            image=cv2.resize(photo,(480,480));image=image[:,::-1] if mirror else image
            canvas=np.zeros((480,640,3),np.uint8);canvas[:,80:560]=image
            frame=temp/'frame.bgra';frame.write_bytes(cv2.cvtColor(canvas,cv2.COLOR_BGR2BGRA).tobytes())
            results=json.loads(subprocess.check_output([str(cli),str(bundle),str(frame),'640','480'],text=True))
            for hands in results:
                for h in hands:
                    xyz=np.asarray(h['world']);uv=np.asarray(h['landmarks'])
                    assert xyz.shape==(21,3) and uv.shape==(21,3) and np.isfinite(xyz).all() and np.isfinite(uv).all()
                    assert h['side'] in (1,2) and .02<np.linalg.norm(xyz[9]-xyz[0])<.2
                    assert np.linalg.norm(xyz[0])<1e-5
            reports.append({'photo':p.name,'mirror':mirror,'hand_counts':[len(h) for h in results]})
    if not any(any(c>0 for c in r['hand_counts']) for r in reports):raise AssertionError('Vision did not detect any real test hand')
report={'native_mobrecon':'PASS','compute':'macOS CPU_ONLY; no iPhone/ANE benchmark','cases':reports}
(root/'ios/build/native-smoke.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
