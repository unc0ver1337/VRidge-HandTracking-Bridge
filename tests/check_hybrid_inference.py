"""Execute production Vision extraction and Core ML finger-only path on photos.

macOS CPU fixture check. This is not an iPhone throughput/camera/VRidge test.
"""
from pathlib import Path
import json,plistlib,shutil,subprocess,tempfile
import cv2,numpy as np

root=Path(__file__).resolve().parents[1]
cli=root/'ios/build/hybrid_image_test'
subprocess.run(['clang++','-std=c++17','-O2','-fobjc-arc','-fblocks',str(root/'tests/hybrid_image.mm'),str(root/'ios/Tracking/CoreMLTracker.mm'),'-framework','Foundation','-framework','CoreML','-framework','CoreVideo','-framework','Vision','-framework','ImageIO','-o',str(cli)],check=True)
with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp);bundle=temp/'Models.bundle';bundle.mkdir()
    (bundle/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'test.hybrid','CFBundlePackageType':'BNDL'}))
    # Deliberately no palm detector: the production finger path must not need it.
    shutil.copytree(root/'ios/build/host/hand_landmarks_detector.mlmodelc',bundle/'hand_landmarks_detector.mlmodelc')
    image=cv2.resize(cv2.imread(str(root/'ios/assets/reference/armandhand.JPG')),(640,480))
    report=[]
    for label,photo in [('original',image),('mirrored',np.ascontiguousarray(image[:,::-1]))]:
        path=temp/'frame.bgra';path.write_bytes(cv2.cvtColor(photo,cv2.COLOR_BGR2BGRA).tobytes())
        hands=json.loads(subprocess.check_output([str(cli),str(bundle),str(path),'640','480'],text=True))
        assert len(hands)>0,(label,'Vision found no confident palm')
        assert any(len(h['world'])==21 for h in hands),(label,'no finger inference from Vision ROIs')
        for hand in hands:
            assert np.asarray(hand['vision']).shape==(21,3)
            assert np.isfinite(hand['vision']).all()
            if hand['world']:assert np.isfinite(hand['world']).all()
        report.append({'image':label,'hands':hands})
    output={'result':'PASS','platform':'macOS CPU fixture, not iPhone FPS','cases':report}
    (root/'ios/build/hybrid-smoke.json').write_text(json.dumps(output,indent=2))
    print(json.dumps({'result':'PASS','cases':[(v['image'],len(v['hands'])) for v in report]}))
