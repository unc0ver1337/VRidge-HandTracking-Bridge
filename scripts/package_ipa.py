"""Local/private IPA packaging. Never fetch or publish proprietary app content.

Append LC_LOAD_DYLIB only in verified zero-filled Mach-O header slack. All existing
code/data offsets remain unchanged. Signing is deliberately a separate, explicit step.
"""
import argparse,plistlib,struct,zipfile,tempfile,shutil,subprocess,sys,os
from pathlib import Path

LOAD_PATH='@executable_path/Frameworks/VRidgeHandTracking.dylib'

def mediapipe_info(info):
    info['CFBundleDisplayName']='VRidge Hand Tracking'
    info['NSCameraUsageDescription']='Ultra-wide camera tracks your hands with MediaPipe while VRidge streams VR.'
    info['NSLocalNetworkUsageDescription']='Find the GlassVR iPhone Bridge and stream hand tracking.'
    info['NSBonjourServices']=sorted((set(info.get('NSBonjourServices',[]))-{'_vhbridge._udp'})|{'_mpbridge._udp'})
    if int(str(info.get('MinimumOSVersion','0')).split('.')[0])<15:info['MinimumOSVersion']='15.0'
    return info

def inject(data):
    b=bytearray(data)
    if len(b)<32 or struct.unpack_from('<I',b)[0]!=0xfeedfacf: raise ValueError('requires thin 64-bit little-endian Mach-O')
    if struct.unpack_from('<I',b,4)[0]!=0x100000c: raise ValueError('requires ARM64')
    n,cmdbytes=struct.unpack_from('<II',b,16); off=32; commands=[]; first_data=len(b)
    for _ in range(n):
        cmd,size=struct.unpack_from('<II',b,off)
        if size<8 or size%8 or off+size>32+cmdbytes: raise ValueError('malformed Mach-O command')
        if cmd==0x2c and struct.unpack_from('<I',b,off+16)[0]!=0: raise ValueError('encrypted executable; use a legally obtained decrypted IPA')
        if cmd==0x19: # LC_SEGMENT_64 and its file-backed sections
            nsects=struct.unpack_from('<I',b,off+64)[0]
            if size!=72+nsects*80: raise ValueError('malformed segment')
            for j in range(nsects):
                sec=off+72+80*j; offset=struct.unpack_from('<I',b,sec+48)[0]
                if offset>0: first_data=min(first_data,offset)
        if cmd in (0xc,0x80000018,0x8000001f):
            nameoff=struct.unpack_from('<I',b,off+8)[0]
            name=bytes(b[off+nameoff:off+size]).split(b'\0')[0]
            if name==LOAD_PATH.encode(): raise ValueError('already injected')
        if cmd!=0x1d: commands.append(bytes(b[off:off+size])) # discard invalid old LC_CODE_SIGNATURE
        off+=size
    if off!=32+cmdbytes: raise ValueError('load command size mismatch')
    name=LOAD_PATH.encode()+b'\0'; size=(24+len(name)+7)//8*8
    new=struct.pack('<6I',0xc,size,24,0,0x10000,0x10000)+name
    new=new.ljust(size,b'\0'); table=b''.join(commands)+new
    end=32+len(table)
    if end>first_data or end>len(b): raise ValueError('no safe header slack; relinking prohibited')
    if end>off and any(b[off:end]): raise ValueError('nonzero header slack; refusing to overwrite')
    b[32:max(off,end)]=table+b'\0'*max(0,off-end)
    struct.pack_into('<II',b,16,len(commands)+1,len(table))
    return bytes(b)

def package(ipa,dylib,output,settings,identity=None,profile=None,entitlements=None):
    if identity and (sys.platform!='darwin' or not profile or not entitlements): raise ValueError('signing requires macOS, identity, provisioning profile and matching entitlements')
    with tempfile.TemporaryDirectory(prefix='vh-private-') as temp:
        root=Path(temp)
        with zipfile.ZipFile(ipa) as archive:
            for item in archive.infolist():
                if not (root/item.filename).resolve().is_relative_to(root.resolve()): raise ValueError('unsafe zip path')
            archive.extractall(root)
        apps=list((root/'Payload').glob('*.app'))
        if len(apps)!=1: raise ValueError('expected exactly one app')
        app=apps[0]; plist=app/'Info.plist'; info=plistlib.loads(plist.read_bytes())
        binary=app/info['CFBundleExecutable']
        if not binary.resolve().is_relative_to(app.resolve()): raise ValueError('invalid executable path')
        binary.write_bytes(inject(binary.read_bytes())); binary.chmod(0o755)
        frameworks=app/'Frameworks'; frameworks.mkdir(exist_ok=True)
        shutil.copy2(dylib,frameworks/'VRidgeHandTracking.dylib'); shutil.copy2(settings,app/'VHBridge.plist')
        shutil.copy2(Path(dylib).parent/'hand_landmarker.task',app/'hand_landmarker.task')
        mediapipe_info(info)
        plist.write_bytes(plistlib.dumps(info))
        for signature in app.rglob('_CodeSignature'):
            if signature.is_dir(): shutil.rmtree(signature)
        old=app/'embedded.mobileprovision'
        if old.exists(): old.unlink()
        if identity:
            shutil.copy2(profile,old)
            ent=plistlib.loads(Path(entitlements).read_bytes())
            decoded=subprocess.check_output(['security','cms','-D','-i',str(profile)])
            p=plistlib.loads(decoded); permitted=p['Entitlements']; appid=permitted['application-identifier']
            expected=appid.split('.',1)[0]+'.'+info['CFBundleIdentifier']
            import fnmatch
            if not fnmatch.fnmatchcase(expected,appid) or ent.get('application-identifier')!=expected: raise ValueError('profile/entitlements do not match VRidge bundle ID')
            # Nested frameworks and dylibs first, app last. Never --deep-sign blindly.
            nested=sorted([x for x in frameworks.rglob('*') if x.suffix in ('.framework','.dylib')],key=lambda x:len(x.parts),reverse=True)
            for item in nested: subprocess.run(['codesign','--force','--sign',identity,str(item)],check=True)
            subprocess.run(['codesign','--force','--sign',identity,'--entitlements',str(entitlements),str(app)],check=True)
            subprocess.run(['codesign','--verify','--deep','--strict',str(app)],check=True)
        output=Path(output); output.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
            for item in root.rglob('*'):
                if item.is_file(): archive.write(item,item.relative_to(root).as_posix())
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--ipa',required=True);p.add_argument('--dylib',required=True);p.add_argument('--output',required=True)
    p.add_argument('--settings',default='ios/VHBridge.plist');p.add_argument('--identity');p.add_argument('--profile');p.add_argument('--entitlements')
    args=p.parse_args(); out=package(**vars(args)); print(f'{out}: '+('signed and verified' if args.identity else 'UNSIGNED; requires compatible jailbreak/TrollStore or complete re-signing before install'))
