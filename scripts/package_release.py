"""Create the release bundle; never install or launch anything."""
import argparse,hashlib,json,plistlib,struct,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BUNDLE_ID='com.riftcat.vridge2'

def package(ipa,windows,ios,output,commit,ci_run):
    ipa,windows,ios,output=map(Path,(ipa,windows,ios,output))
    if not (windows/'VRidgeHandBridge.exe').is_file():raise ValueError('missing Windows EXE')
    library=(ios/'VRidgeHandTracking.dylib').read_bytes()
    if struct.unpack_from('<II',library)!=(0xfeedfacf,0x100000c):raise ValueError('requires ARM64 Mach-O dylib')
    model=(ios/'hand_landmarker.task').read_bytes()
    if hashlib.sha256(model).hexdigest()!='fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1':raise ValueError('unexpected model')
    with zipfile.ZipFile(ipa) as archive:
        if archive.testzip():raise ValueError('corrupt IPA')
        name=next(n for n in archive.namelist() if n.startswith('Payload/') and n.count('/')==2 and n.endswith('/Info.plist'))
        root=name.rsplit('/',1)[0];info=plistlib.loads(archive.read(name))
        if info['CFBundleIdentifier']!=BUNDLE_ID:raise ValueError('unexpected VRidge bundle ID')
        if archive.read(root+'/Frameworks/VRidgeHandTracking.dylib')!=library:raise ValueError('IPA/dylib mismatch')
        if archive.read(root+'/hand_landmarker.task')!=model:raise ValueError('IPA/model mismatch')
        if any('/_CodeSignature/' in n or n.endswith('/embedded.mobileprovision') for n in archive.namelist()):raise ValueError('bundle is expected to be unsigned')
    files={}
    for path in windows.rglob('*'):
        if path.is_file():files['Windows/'+path.relative_to(windows).as_posix()]=path.read_bytes()
    files['Windows/config.yaml']=(ROOT/'pc/config.yaml').read_bytes()
    files['Windows/Start-Bridge.cmd']=b'@echo off\r\ncd /d "%~dp0"\r\nVRidgeHandBridge.exe --config config.yaml\r\npause\r\n'
    files['Windows/Allow-Local-Network.ps1']=(ROOT/'scripts/allow_local_network.ps1').read_bytes()
    files['iOS/VRidge-HandTracking-2.0-Unsigned.ipa']=ipa.read_bytes()
    for name in ('VRidgeHandTracking.dylib','hand_landmarker.task','load-commands.txt'):
        files['iOS/library/'+name]=(ios/name).read_bytes()
    files['GlassVR/driver_glassvr.dll']=(ROOT/'artifacts/driver_glassvr-visibility-fix.dll').read_bytes()
    for path in (ROOT/'patches').glob('*.patch'):files['GlassVR/patches/'+path.name]=path.read_bytes()
    for path in (ROOT/'docs').glob('*.md'):files['docs/'+path.name]=path.read_bytes()
    for name in ('README.md','THIRD_PARTY.md','LICENSE','docs/VALIDATION.md','third_party/MediaPipe-LICENSE.txt'):
        files[name]=(ROOT/name).read_bytes()
    files['BUILD.json']=json.dumps({'project':'VRidge Hand Tracking Bridge','version':'2.0.0','source_commit':commit,'ci_run':ci_run,'ipa_signed':False,'device_verified':False,'bundle_id':BUNDLE_ID,'network':'MPBR/v2 UDP39580','hardware_runtime_started_during_build':False},indent=2).encode()
    files['SHA256SUMS.txt']=''.join(hashlib.sha256(data).hexdigest()+'  '+name+'\n' for name,data in sorted(files.items())).encode()
    output.parent.mkdir(exist_ok=True,parents=True)
    temp=output.with_suffix('.zip.tmp')
    try:
        with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
            for name,data in files.items():archive.writestr(name,data)
        with zipfile.ZipFile(temp) as archive:
            if archive.testzip():raise ValueError('corrupt release archive')
        temp.replace(output)
    finally:temp.unlink(missing_ok=True)
    checksum=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256').write_text(checksum+'  '+output.name+'\n',encoding='ascii')
    print(json.dumps({'path':str(output),'files':len(files),'bytes':output.stat().st_size,'sha256':checksum},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ipa','windows','ios','output','commit','ci-run'):parser.add_argument('--'+name,required=True)
    package(**vars(parser.parse_args()))
