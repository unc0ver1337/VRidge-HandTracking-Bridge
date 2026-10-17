"""Update a copy of an injected IPA with native Core ML backend/models."""
import argparse,hashlib,json,plistlib,struct,zipfile
from pathlib import Path
from scripts.package_ipa import LOAD_PATH

def package(ipa,build,output):
    ipa,build,output=map(Path,(ipa,build,output));output.parent.mkdir(parents=True,exist_ok=True)
    if ipa.resolve()==output.resolve():raise ValueError('input IPA must be preserved')
    library=(build/'VRidgeHandTracking.dylib').read_bytes()
    if struct.unpack_from('<II',library)!=(0xfeedfacf,0x100000c):raise ValueError('ARM64 dylib required')
    resources={}
    for name in ('hand_detector','hand_landmarks_detector'):
        model=build/(name+'.mlmodelc')
        if not model.is_dir() or not any(p.is_file() for p in model.rglob('*')):raise ValueError('missing compiled model '+name)
        for p in model.rglob('*'):
            if p.is_file():resources[p.relative_to(build).as_posix()]=p.read_bytes()
    with zipfile.ZipFile(ipa) as source:
        if source.testzip():raise ValueError('corrupt input IPA')
        names=source.namelist();plists=[n for n in names if n.startswith('Payload/') and n.count('/')==2 and n.endswith('/Info.plist')]
        if len(plists)!=1:raise ValueError('requires one app')
        root=plists[0].rsplit('/',1)[0];info=plistlib.loads(source.read(plists[0]));exe=root+'/'+info['CFBundleExecutable'];binary=source.read(exe)
        if binary.count(LOAD_PATH.encode())!=1:raise ValueError('requires already-injected IPA')
        if root+'/Frameworks/VRidgeHandTracking.dylib' not in names:raise ValueError('missing original tweak')
        info['CFBundleIdentifier']='com.riftcat.vridge2.coreml.preview';info['CFBundleDisplayName']='VRidge Core ML Test';info['MinimumOSVersion']='16.0'
        info.pop('CFBundleURLTypes',None) # Avoid claiming stable app URL schemes.
        info['NSBonjourServices']=sorted((set(info.get('NSBonjourServices',[]))-{'_vhbridge._udp'})|{'_mpbridge._udp'})
        replacements={plists[0]:plistlib.dumps(info),root+'/Frameworks/VRidgeHandTracking.dylib':library}
        replacements.update({root+'/'+n:data for n,data in resources.items()})
        temp=output.with_suffix('.ipa.tmp')
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as result:
                written=set()
                for entry in source.infolist():
                    name=entry.filename
                    if '/_CodeSignature/' in name or name.endswith('/embedded.mobileprovision') or name==root+'/hand_landmarker.task':continue
                    if name.startswith((root+'/hand_detector.mlmodelc/',root+'/hand_landmarks_detector.mlmodelc/')):continue
                    result.writestr(entry,replacements.get(name,source.read(name)));written.add(name)
                for name,data in replacements.items():
                    if name not in written:result.writestr(name,data)
            with zipfile.ZipFile(temp) as result:
                if result.testzip():raise ValueError('corrupt output')
                assert result.read(exe)==binary
                for name,data in replacements.items():assert result.read(name)==data
            temp.replace(output)
        finally:temp.unlink(missing_ok=True)
    print(json.dumps({'ipa':str(output),'signed':False,'bundle_id':info['CFBundleIdentifier'],'models':len(resources),'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'executable_preserved':True},indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('ipa','build','output'):parser.add_argument('--'+name,required=True)
    package(**vars(parser.parse_args()))
