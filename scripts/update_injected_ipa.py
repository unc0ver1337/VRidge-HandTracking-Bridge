"""Update our dylib/settings in an already injected, unsigned IPA."""
import argparse,plistlib,zipfile,struct,os
from pathlib import Path
from scripts.package_ipa import LOAD_PATH,mediapipe_info

def update(ipa,dylib,settings,output):
    output=Path(output);temp=output.with_suffix('.ipa.tmp')
    with zipfile.ZipFile(ipa) as source:
        names=source.namelist()
        plists=[n for n in names if n.startswith('Payload/') and n.count('/')==2 and n.endswith('/Info.plist')]
        if len(plists)!=1:raise ValueError('requires one top-level app')
        root=plists[0].rsplit('/',1)[0];info=plistlib.loads(source.read(plists[0]))
        binary=source.read(root+'/'+info['CFBundleExecutable'])
        if len(binary)<32 or struct.unpack_from('<I',binary)[0]!=0xfeedfacf:raise ValueError('requires ARM64 Mach-O')
        count,size=struct.unpack_from('<II',binary,16);off=32;loads=[]
        for _ in range(count):
            cmd,length=struct.unpack_from('<II',binary,off)
            if length<8 or off+length>32+size:raise ValueError('bad load command')
            if cmd==12:
                pos=struct.unpack_from('<I',binary,off+8)[0]
                loads.append(binary[off+pos:off+length].split(b'\0')[0])
            off+=length
        if loads.count(LOAD_PATH.encode())!=1:raise ValueError('our dylib must already be injected exactly once')
        replacements={root+'/Frameworks/VRidgeHandTracking.dylib':Path(dylib).read_bytes(),root+'/VHBridge.plist':Path(settings).read_bytes()}
        replacements[root+'/hand_landmarker.task']=(Path(dylib).parent/'hand_landmarker.task').read_bytes()
        mediapipe_info(info)
        replacements[plists[0]]=plistlib.dumps(info)
        if root+'/Frameworks/VRidgeHandTracking.dylib' not in names:raise ValueError('missing injected dylib')
        try:
            with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as dest:
                for entry in source.infolist():
                    if '/_CodeSignature/' in entry.filename or entry.filename.endswith('/embedded.mobileprovision'):continue
                    dest.writestr(entry,replacements.get(entry.filename,source.read(entry.filename)))
                for name,data in replacements.items():
                    if name not in names:dest.writestr(name,data)
            with zipfile.ZipFile(temp) as result:
                if result.testzip() is not None:raise ValueError('corrupt output')
                if result.read(root+'/'+info['CFBundleExecutable'])!=binary:raise ValueError('executable changed')
        except BaseException:
            temp.unlink(missing_ok=True);raise
    os.replace(temp,output)
    print(str(output)+': updated UNSIGNED IPA; executable preserved')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--ipa',required=True);p.add_argument('--dylib',required=True);p.add_argument('--settings',default='ios/VHBridge.plist');p.add_argument('--output',required=True)
    update(**vars(p.parse_args()))
