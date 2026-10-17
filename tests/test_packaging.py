import struct,pytest,zipfile,plistlib
from scripts.package_ipa import inject,LOAD_PATH,package

def macho(encrypted=0,slack=True):
    # One section at offset 4096 with a recognizable nonzero body.
    header=struct.pack('<8I',0xfeedfacf,0x100000c,0,2,2,176,0,0)
    segment=struct.pack('<II16s4Q4I',0x19,152,b'__TEXT',0,8192,0,8192,7,5,1,0)
    section=struct.pack('<16s16sQQ8I',b'__text',b'__TEXT',4096,16,4096,2,0,0,0,0,0,0)
    crypt=struct.pack('<6I',0x2c,24,4096,16,encrypted,0)
    body=(header+segment+section+crypt).ljust(4096,b'\0')+b'CODE_NOT_CHANGED'
    if not slack:body=body[:208]+b'X'*500+body[708:]
    return body

def test_inject_preserves_code_and_adds_load_command():
    original=macho();result=inject(original)
    assert result[4096:]==original[4096:];assert LOAD_PATH.encode() in result
    assert struct.unpack_from('<I',result,16)[0]==3
    with pytest.raises(ValueError):inject(result)

def test_inject_refuses_encryption_and_occupied_slack():
    with pytest.raises(ValueError):inject(macho(1))
    with pytest.raises(ValueError):inject(macho(slack=False))

def test_complete_private_packaging_metadata_and_preservation(tmp_path):
    source=tmp_path/'source.ipa';dylib=tmp_path/'tracker.dylib';settings=tmp_path/'settings.plist';out=tmp_path/'out.ipa'
    dylib.write_bytes(b'SYNTHETIC_TEST_LIBRARY');settings.write_bytes(plistlib.dumps({'FPS':30}))
    (tmp_path/'hand_landmarker.task').write_bytes(b'SYNTHETIC_MODEL')
    info={'CFBundleExecutable':'Original','CFBundleIdentifier':'example.original','CFBundleURLTypes':[{'CFBundleURLSchemes':['original']}],'MinimumOSVersion':'11.0','NSBonjourServices':['_original._udp']}
    with zipfile.ZipFile(source,'w') as z:
        z.writestr('Payload/Original.app/Info.plist',plistlib.dumps(info));z.writestr('Payload/Original.app/Original',macho());z.writestr('Payload/Original.app/resource.bin',b'KEEP_ORIGINAL_RESOURCE')
    original=source.read_bytes();package(source,dylib,out,settings)
    assert source.read_bytes()==original
    with zipfile.ZipFile(out) as z:
        pl=plistlib.loads(z.read('Payload/Original.app/Info.plist'))
        assert pl['CFBundleIdentifier']=='example.original' and pl['MinimumOSVersion']=='15.0'
        assert pl['NSBonjourServices']==['_mpbridge._udp','_original._udp']
        assert pl['CFBundleURLTypes']==info['CFBundleURLTypes']
        assert z.read('Payload/Original.app/hand_landmarker.task')==b'SYNTHETIC_MODEL'
        assert z.read('Payload/Original.app/Original')[4096:]==macho()[4096:]
        assert z.read('Payload/Original.app/resource.bin')==b'KEEP_ORIGINAL_RESOURCE'

def test_update_injected_ipa_preserves_executable(tmp_path):
    from scripts.update_injected_ipa import update
    original=tmp_path/'in.ipa';output=tmp_path/'out.ipa';dll=tmp_path/'new.dylib';settings=tmp_path/'settings.plist'
    (tmp_path/'hand_landmarker.task').write_bytes(b'MODEL')
    binary=inject(macho());dll.write_bytes(b'NEW_DYLIB');settings.write_bytes(plistlib.dumps({'FPS':30}))
    root='Payload/App.app/'
    with zipfile.ZipFile(original,'w') as z:
        z.writestr(root+'Info.plist',plistlib.dumps({'CFBundleExecutable':'App','CFBundleIdentifier':'com.riftcat.vridge2.test'}))
        z.writestr(root+'App',binary);z.writestr(root+'Frameworks/VRidgeHandTracking.dylib',b'OLD')
        z.writestr(root+'VHBridge.plist',b'OLD');z.writestr(root+'_CodeSignature/CodeResources',b'OLD_SIGNATURE')
    update(original,dll,settings,output)
    with zipfile.ZipFile(output) as z:
        assert z.read(root+'App')==binary
        assert z.read(root+'Frameworks/VRidgeHandTracking.dylib')==b'NEW_DYLIB'
        assert plistlib.loads(z.read(root+'VHBridge.plist'))['FPS']==30
        assert plistlib.loads(z.read(root+'Info.plist'))['CFBundleIdentifier']=='com.riftcat.vridge2.test'
        assert z.read(root+'hand_landmarker.task')==b'MODEL'
        assert root+'_CodeSignature/CodeResources' not in z.namelist()
