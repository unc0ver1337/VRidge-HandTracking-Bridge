"""Fetch immutable upstream Core ML assets; no PyTorch/pickle loading."""
from pathlib import Path
import hashlib,urllib.request,json
ROOT=Path(__file__).resolve().parent
COMMIT='565d18818104a315887c611c84125f382dfcf6aa'
FILES=[('models/hand_detector.mlpackage/Manifest.json', 'c8334589fe08fc59fc75c741ca2ad46cb3bf9ab1a121c40933492f6a5abdf97c'), ('models/hand_detector.mlpackage/Data/com.apple.CoreML/model.mlmodel', 'd59f5ef0a0e9876dd5c3c29a9f9a79b5e69b4bccc268e565a678ebb601b8e40d'), ('models/hand_detector.mlpackage/Data/com.apple.CoreML/weights/weight.bin', '5bda5212ad6cfcb8d19c95c4589564e6eaf241627c7aed95bf0b4a3ddbd06943'), ('models/hand_landmarks_detector.mlpackage/Manifest.json', 'ce2d0e77dd317f6534d20fceeadbb1d5a9dd396fdb3c3a8ba178693a9132a803'), ('models/hand_landmarks_detector.mlpackage/Data/com.apple.CoreML/model.mlmodel', '9bec43dfa3555c74ff85d189e5ec42b70adb8ff3b364ebca22917e9009d25d33'), ('models/hand_landmarks_detector.mlpackage/Data/com.apple.CoreML/weights/weight.bin', '0649c8a900c3cfb630d5c8b94b137969c1221a4141f1016d0f2999807ab76428'), ('src/fasthands/pipeline.py', 'f308b793a6d52b6e41946849e2a35f5d5582b0bac4f413db057e946ba35ca38b'), ('LICENSE', '4534b881ba47ec03d8cff3838078e6665a41c875792a33666741b18c361ab9ce'), ('test_images/armandhand.JPG', '37086da2ab449fc6e1803d44beb80197a3fc1c53ca836bded51aa6a732cab22e')]
for name,sha in FILES:
    if name.startswith('models/'):dest=ROOT/'assets'/name.removeprefix('models/')
    else:dest=ROOT/'assets/reference'/Path(name).name
    dest.parent.mkdir(parents=True,exist_ok=True)
    if not dest.exists() or hashlib.sha256(dest.read_bytes()).hexdigest()!=sha:
        dest.write_bytes(urllib.request.urlopen('https://raw.githubusercontent.com/VimalMollyn/Mediapipe-Hands-PyTorch-CoreML/'+COMMIT+'/'+name,timeout=90).read())
    if hashlib.sha256(dest.read_bytes()).hexdigest()!=sha:raise ValueError('Core ML asset checksum '+name)
print(json.dumps({'upstream_commit':COMMIT,'verified_files':len(FILES)}))
