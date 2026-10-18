import json
from pathlib import Path
from pc.glassvr.install import DriverManager
import pytest

def layout(tmp_path):
    runtime=tmp_path/'SteamVR';tool=runtime/'bin/win64/vrpathreg.exe';tool.parent.mkdir(parents=True);tool.write_bytes(b'TEST')
    source=tmp_path/'bundled';(source/'bin/win64').mkdir(parents=True)
    (source/'driver.vrdrivermanifest').write_text(json.dumps({'name':'glassvr'}))
    (source/'bin/win64/driver_glassvr.dll').write_bytes(b'TEST_DLL')
    paths=tmp_path/'openvrpaths.vrpath';paths.write_text(json.dumps({'runtime':[str(runtime)],'external_drivers':[]}))
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        if 'adddriver' in args:
            data=json.loads(paths.read_text());data['external_drivers'].append(args[-1]);paths.write_text(json.dumps(data))
        if 'removedriver' in args:
            data=json.loads(paths.read_text());data['external_drivers'].remove(args[-1]);paths.write_text(json.dumps(data))
    manager=DriverManager(paths,source,tmp_path/'managed/glassvrdriver',run,lambda _:None)
    manager.configure_channels=lambda:None
    return manager,calls

def test_absent_driver_installs_then_waits_without_launching_steam(tmp_path):
    m,calls=layout(tmp_path);order=[]
    m.shutdown_steam=lambda:order.append('close')
    m.wait_for_steamvr=lambda:order.append('wait')
    m.ensure_and_wait()
    assert order==['close','wait'] and m.registered()==[m.managed]
    assert calls[0][1]=='adddriver'
    assert (m.managed/'bin/win64/driver_glassvr.dll').read_bytes()==b'TEST_DLL'

def test_registered_driver_never_closes_steam_and_uninstall_preserves_files(tmp_path):
    m,calls=layout(tmp_path)
    data=m.paths();data['external_drivers']=[str(m.bundled)];m.paths_file.write_text(json.dumps(data))
    m.shutdown_steam=lambda:pytest.fail('must not close Steam')
    m.wait_for_steamvr=lambda:None
    m.ensure_and_wait();assert not calls
    m.uninstall();assert not m.registered() and m.valid(m.bundled)

def test_missing_bundle_or_runtime_never_closes_steam(tmp_path):
    m,_=layout(tmp_path);m.shutdown_steam=lambda:pytest.fail('must validate before closing Steam')
    (m.bundled/'bin/win64/driver_glassvr.dll').unlink()
    with pytest.raises(RuntimeError,match='Bundled'):m.install()

def test_cleanup_cannot_remove_outside_managed_staging(tmp_path):
    m,_=layout(tmp_path)
    with pytest.raises(ValueError):m.remove_staging(tmp_path)
