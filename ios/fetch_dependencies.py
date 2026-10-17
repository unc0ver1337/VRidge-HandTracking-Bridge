"""Fetch immutable upstream Core ML assets; no PyTorch/pickle loading."""
from pathlib import Path
import hashlib,urllib.request,json
ROOT=Path(__file__).resolve().parent
COMMIT='565d18818104a315887c611c84125f382dfcf6aa'
FILES=[('models/hand_detector.mlpackage/Manifest.json', '52e6429243e3e11626667365a2c0ed43fe11c9fce886df62227a6df0a964b50e'), ('models/hand_detector.mlpackage/Data/com.apple.CoreML/model.mlmodel', 'd59f5ef0a0e9876dd5c3c29a9f9a79b5e69b4bccc268e565a678ebb601b8e40d'), ('models/hand_detector.mlpackage/Data/com.apple.CoreML/weights/weight.bin', '5bda5212ad6cfcb8d19c95c4589564e6eaf241627c7aed95bf0b4a3ddbd06943'), ('models/hand_landmarks_detector.mlpackage/Manifest.json', 'b513c4e7616b6d2442fc3b8666cb9d3587e238e88a8e6fc859b16d4b11306787'), ('models/hand_landmarks_detector.mlpackage/Data/com.apple.CoreML/model.mlmodel', '9bec43dfa3555c74ff85d189e5ec42b70adb8ff3b364ebca22917e9009d25d33'), ('models/hand_landmarks_detector.mlpackage/Data/com.apple.CoreML/weights/weight.bin', '0649c8a900c3cfb630d5c8b94b137969c1221a4141f1016d0f2999807ab76428'), ('src/fasthands/pipeline.py', '963fd41501772c76dd6c1e119bbba35eb398921f2e4f83884baa8110a1c6bc94'), ('LICENSE', 'ff46667386d0817d565edfa722e623e1a9ee324f98f002105197f8f50d8a9b61'), ('test_images/armandhand.JPG', '37086da2ab449fc6e1803d44beb80197a3fc1c53ca836bded51aa6a732cab22e')]
for name,sha in FILES:
    if name.startswith('models/'):dest=ROOT/'assets'/name.removeprefix('models/')
    else:dest=ROOT/'assets/reference'/Path(name).name
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest()!=sha:
        dest.write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/VimalMollyn/Mediapipe-Hands-PyTorch-CoreML/'+COMMIT+'/'+name,timeout=90).read())
    if hashlib.sha256(dest.read_bytes()).hexdigest()!=sha:raise ValueError('Core ML asset checksum '+name)
print(json.dumps({'upstream_commit':COMMIT,'verified_files':len(FILES)}))
