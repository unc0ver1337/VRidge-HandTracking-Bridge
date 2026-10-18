"""Visible, explicit bootstrap for the bundled GlassVR driver. No import side effects."""
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

LOG = logging.getLogger(__name__)
NAME = 'glassvr'

def read_json(path, default):
    try: return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError): return default

class DriverManager:
    def __init__(self, paths_file=None, bundled=None, managed=None, runner=subprocess.run, sleep=time.sleep):
        app = Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(__file__).resolve().parents[2]
        self.paths_file = Path(paths_file) if paths_file else Path(os.environ.get('LOCALAPPDATA',''))/'openvr/openvrpaths.vrpath'
        self.bundled = Path(bundled) if bundled else app/'GlassVR/glassvrdriver'
        self.managed = Path(managed) if managed else Path(os.environ.get('LOCALAPPDATA',''))/'VRidgeHandBridge/driver/glassvrdriver'
        self.run = runner; self.sleep = sleep

    def paths(self): return read_json(self.paths_file,{})

    def valid(self, root):
        root = Path(root)
        manifest = read_json(root/'driver.vrdrivermanifest',{})
        return manifest.get('name') == NAME and (root/'bin/win64/driver_glassvr.dll').is_file()

    def registered(self):
        data=self.paths();roots=[Path(p) for p in data.get('external_drivers',[])]
        for runtime in data.get('runtime',[]):
            folder=Path(runtime)/'drivers'
            if folder.is_dir():roots.extend(p for p in folder.iterdir() if p.is_dir())
        return list(dict.fromkeys(p.resolve() for p in roots if self.valid(p)))

    def tool(self):
        for root in self.paths().get('runtime',[]):
            path = Path(root)/'bin/win64/vrpathreg.exe'
            if path.is_file(): return path
        raise RuntimeError('SteamVR runtime not found. Install/run SteamVR once, then retry.')

    def shutdown_steam(self):
        LOG.warning('Driver missing: closing Steam and SteamVR to register GlassVR.')
        # Ask Steam to close first; only its VR processes and client may be ended.
        steam = None
        if os.name == 'nt':
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Valve\Steam') as key:
                    steam = Path(winreg.QueryValueEx(key,'SteamPath')[0])/'steam.exe'
            except OSError: steam = None
        if steam and steam.is_file():
            self.run([str(steam),'-shutdown'],check=False,timeout=20)
            self.sleep(3)
        for name in ('vrmonitor.exe','vrserver.exe','vrcompositor.exe','vrstartup.exe','steam.exe'):
            self.run(['taskkill','/IM',name,'/T'],capture_output=True,check=False,timeout=10)
        self.sleep(2)
        for name in ('vrmonitor.exe','vrserver.exe','vrcompositor.exe','vrstartup.exe','steam.exe'):
            self.run(['taskkill','/F','/IM',name,'/T'],capture_output=True,check=False,timeout=10)

    def install(self):
        if not self.valid(self.bundled): raise RuntimeError('Bundled GlassVR driver missing or incomplete; extract the ENTIRE release ZIP.')
        tool = self.tool() # Fail before closing any application if SteamVR is absent.
        self.shutdown_steam()
        self.managed.parent.mkdir(parents=True,exist_ok=True)
        staging = self.managed.with_name(self.managed.name+'.installing')
        # Fixed sibling inside the managed driver directory, never a user argument.
        if staging.exists(): self.remove_staging(staging)
        shutil.copytree(self.bundled,staging)
        if not self.valid(staging): raise RuntimeError('Copied driver verification failed')
        if self.managed.exists():
            backup=self.managed.with_name(self.managed.name+'.previous')
            if backup.exists(): self.remove_staging(backup)
            self.managed.rename(backup)
        staging.rename(self.managed)
        self.run([str(tool),'adddriver',str(self.managed)],check=True,timeout=20)
        if not any(p.resolve()==self.managed.resolve() for p in self.registered()):
            raise RuntimeError('SteamVR did not register the copied GlassVR driver')
        LOG.info('GlassVR installed at %s',self.managed)

    def remove_staging(self,path):
        path=Path(path)
        if path.is_symlink() or path.resolve().parent!=self.managed.parent.resolve() or path.name not in (self.managed.name+'.installing',self.managed.name+'.previous'):
            raise ValueError('refusing removal outside managed staging directories')
        shutil.rmtree(path)

    def wait_for_steamvr(self):
        import openvr
        LOG.info('Waiting: launch Steam and SteamVR yourself. Ctrl+C cancels.')
        while True:
            initialized=False
            try:
                openvr.init(openvr.VRApplication_Background);initialized=True
                openvr.VRSystem().getRuntimeVersion()
                LOG.info('SteamVR is ready');return
            except Exception:
                self.sleep(1)
            finally:
                if initialized:openvr.shutdown()

    def ensure_and_wait(self):
        self.configure_channels()
        self.configure_multiple_drivers()
        if not self.registered():
            self.install()
        else: LOG.info('GlassVR driver already registered: %s',self.registered())
        self.wait_for_steamvr()

    def configure_multiple_drivers(self):
        configs=self.paths().get('config',[])
        if not configs:raise RuntimeError('SteamVR config path missing. Run SteamVR once before installation.')
        path=Path(configs[0])/'steamvr.vrsettings'
        data=json.loads(path.read_text(encoding='utf8')) if path.exists() else {}
        settings=data.setdefault('steamvr',{})
        if settings.get('activateMultipleDrivers') is True:return
        if path.exists():shutil.copy2(path,path.with_name('steamvr.before-vridge-bridge.vrsettings'))
        settings['activateMultipleDrivers']=True
        path.parent.mkdir(parents=True,exist_ok=True)
        temporary=path.with_name('steamvr.bridge-install.tmp')
        temporary.write_text(json.dumps(data,indent=2),encoding='utf8');os.replace(temporary,path)
        LOG.info('Enabled SteamVR multiple drivers for VRidge HMD + GlassVR controllers')

    def configure_channels(self,path=None):
        path=Path(path) if path else Path(os.environ.get('APPDATA',''))/'glassvr/settings.json'
        if path.exists():
            # Refuse to replace damaged settings with defaults and lose user data.
            data=json.loads(path.read_text(encoding='utf8'))
        else:data={}
        before=dict(data)
        for side,port in (('cl',9002),('cr',9001)):
            for channel in ('pos','rot','input','skeletal'):data[side+channel+' mode']='UDP'
            data['enable '+side]=True;data['tracking '+side]=False
            data.setdefault(side+' port',port)
        data['hand tracking']=False
        data.setdefault('enable hmd',False)
        if data==before:return
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():shutil.copy2(path,path.with_name('settings.before-bridge.json'))
        temp=path.with_name('settings.install.tmp')
        temp.write_text(json.dumps(data,indent=4),encoding='utf8');os.replace(temp,path)

    def uninstall(self):
        roots = self.registered()
        if not roots: LOG.info('GlassVR driver is not registered');return
        tool=self.tool()
        for root in roots:
            if str(root) in self.paths().get('external_drivers',[]) or any(Path(p).resolve()==root for p in self.paths().get('external_drivers',[])):
                self.run([str(tool),'removedriver',str(root)],check=True,timeout=20)
            else:
                allowed={ (Path(p)/'drivers').resolve() for p in self.paths().get('runtime',[]) }
                if root.parent not in allowed or not self.valid(root):raise ValueError('refusing to move an unrelated driver')
                self.shutdown_steam()
                backup=self.managed.parent/('uninstalled-'+str(time.time_ns()))
                backup.parent.mkdir(parents=True,exist_ok=True)
                shutil.move(str(root),str(backup))
                LOG.info('Internal GlassVR driver moved to %s',backup)
        LOG.info('GlassVR unregistered. Restart SteamVR to unload it. Driver files and other drivers were preserved.')
