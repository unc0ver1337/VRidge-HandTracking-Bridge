import plistlib,struct,zipfile
import pytest
from pathlib import Path
from scripts.update_injected_ipa import update
def package(ipa,build,output):
    settings=build/"settings.plist";settings.write_bytes(plistlib.dumps({"FPS":30}));update(ipa,build/"VRidgeHandTracking.dylib",settings,output)
from scripts.package_ipa import inject
from tests.test_packaging import macho

def test_coreml_preserves_source_and_executable_and_embeds_both_models(tmp_path):
    build=tmp_path/'build';build.mkdir();library=struct.pack('<II',0xfeedfacf,0x100000c)+b'SYNTHETIC_LIBRARY'
    (build/'VRidgeHandTracking.dylib').write_bytes(library)
    for name in ('hand_detector','hand_landmarks_detector'):
        folder=build/(name+'.mlmodelc');folder.mkdir();(folder/'coremldata.bin').write_bytes(b'SYNTHETIC_MODEL')
    source=tmp_path/'source.ipa';output=tmp_path/'preview.ipa';root='Payload/App.app/';binary=inject(macho())
    with zipfile.ZipFile(source,'w') as z:
        z.writestr(root+'Info.plist',plistlib.dumps({'CFBundleIdentifier':'original','CFBundleExecutable':'App','CFBundleURLTypes':[{'CFBundleURLSchemes':['stable']}]}))
        z.writestr(root+'App',binary);z.writestr(root+'Frameworks/VRidgeHandTracking.dylib',b'OLD');z.writestr(root+'hand_landmarker.task',b'OLD_TASK')
        z.writestr(root+'resource.txt',b'KEEP');z.writestr(root+'_CodeSignature/CodeResources',b'OLD_SIGNATURE')
    before=source.read_bytes();package(source,build,output)
    assert source.read_bytes()==before
    with zipfile.ZipFile(output) as z:
        info=plistlib.loads(z.read(root+'Info.plist'));assert info['CFBundleIdentifier']=='original'
        assert info['MinimumOSVersion']=='16.0' and info['CFBundleURLTypes']==[{'CFBundleURLSchemes':['stable']}]
        assert z.read(root+'App')==binary and z.read(root+'resource.txt')==b'KEEP'
        assert z.read(root+'Frameworks/VRidgeHandTracking.dylib')==library
        assert root+'hand_landmarker.task' not in z.namelist()
        assert not any('/_CodeSignature/' in n for n in z.namelist())
        for name in ('hand_detector','hand_landmarks_detector'):assert z.read(root+name+'.mlmodelc/coremldata.bin')==b'SYNTHETIC_MODEL'
    # Updating an already prepared preview must also replace nested model files.
    (build/'hand_detector.mlmodelc/coremldata.bin').write_bytes(b'NEW_MODEL')
    package(output,build,tmp_path/'updated.ipa')
    with zipfile.ZipFile(tmp_path/'updated.ipa') as z:assert z.read(root+'hand_detector.mlmodelc/coremldata.bin')==b'NEW_MODEL'

def test_missing_compiled_models_fail_closed(tmp_path):
    from scripts.package_ipa import model_resources
    with pytest.raises(ValueError,match='missing compiled model'):
        model_resources(tmp_path)

def test_update_refuses_overwriting_input(tmp_path):
    with pytest.raises(ValueError,match='input IPA must be preserved'):
        update(tmp_path/'app.ipa',tmp_path/'lib.dylib',tmp_path/'settings.plist',tmp_path/'app.ipa')
