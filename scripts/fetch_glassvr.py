"""Assemble the existing GlassVR driver without installing or starting it."""
from pathlib import Path
import argparse,hashlib,json,urllib.request,urllib.parse,zipfile,io

ROOT=Path(__file__).resolve().parents[1]
def assemble(destination):
    destination=Path(destination)
    pin=json.loads((ROOT/'third_party/GlassVR-assets.json').read_text())
    for name,sha in pin['files'].items():
        dest=destination/name
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest()==sha:continue
        url='https://raw.githubusercontent.com/DaniXmir/GlassVr/'+pin['upstream_commit']+'/code-glassvrserver/assets/driver%20to%20copy/glassvrdriver/'+urllib.parse.quote(name)
        data=urllib.request.urlopen(url,timeout=120).read()
        if hashlib.sha256(data).hexdigest()!=sha:raise ValueError('GlassVR asset mismatch '+name)
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    dll=destination/'bin/win64/driver_glassvr.dll'
    if hashlib.sha256(dll.read_bytes()).hexdigest()!=pin['patched_dll_sha256']:
        local=ROOT/'artifacts/driver_glassvr-visibility-fix.dll'
        if local.exists() and hashlib.sha256(local.read_bytes()).hexdigest()==pin['patched_dll_sha256']:data=local.read_bytes()
        else:
            archive=urllib.request.urlopen(pin['patched_release_url'],timeout=180).read()
            with zipfile.ZipFile(io.BytesIO(archive)) as z:data=z.read('GlassVR/driver_glassvr.dll')
        if hashlib.sha256(data).hexdigest()!=pin['patched_dll_sha256']:raise ValueError('patched GlassVR DLL mismatch')
        dll.write_bytes(data)
    print('Assembled verified GlassVR driver:',destination)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination');assemble(p.parse_args().destination)
