import hashlib,urllib.request,zipfile,io
from pathlib import Path
root=Path(__file__).resolve().parent;deps=root/'deps';deps.mkdir(exist_ok=True);assets=root/'assets';assets.mkdir(exist_ok=True)
items=[
('MediaPipeTasksCommon','25690f3005c0405a7f27b6d273b4db241811d00fbb01c54004057ee1d0e983d8'),
('MediaPipeTaskGraphs','e4d88ed65c101764ef90281a411b9942f369e48673d448eff1f934e1f68d9633'),
('MediaPipeTasksVision','755390ce853b062536899f0729321156d4cdceb263aa92c4bf3b2dd05fe640e0')]
for name,sha in items:
    url='https://dl.google.com/cpdc/20261013-213039/'+name+'-1.1.1.xcframework.zip'
    print('Downloading',name,flush=True);data=urllib.request.urlopen(url,timeout=180).read()
    if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('SDK checksum '+name)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for n in z.namelist():
            if not (deps/n).resolve().is_relative_to(deps.resolve()):raise ValueError('unsafe dependency path')
        z.extractall(deps)
url='https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
data=urllib.request.urlopen(url,timeout=180).read()
if hashlib.sha256(data).hexdigest()!='fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1':raise ValueError('model checksum')
(assets/'hand_landmarker.task').write_bytes(data)
