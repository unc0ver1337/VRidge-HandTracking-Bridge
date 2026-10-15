"""GlassVR has no UDP validity bit; use its live per-device enable settings."""
import os,json,threading,logging
from pathlib import Path

class Visibility:
    def __init__(self,path=None):
        self.path=Path(path) if path else Path(os.environ['APPDATA'])/'glassvr/settings.json'
        self.desired={1:False,2:False};self.lock=threading.Lock();self.stop=threading.Event()
    def update(self,states):
        with self.lock:self.desired=dict(states)
    def flush(self):
        with self.lock:states=dict(self.desired)
        data=json.loads(self.path.read_text(encoding='utf8'))
        values={'enable cl':states[1],'enable cr':states[2]}
        if all(data.get(k)==v for k,v in values.items()):return
        data.update(values);temp=self.path.with_name('settings.bridge-visibility.tmp')
        temp.write_text(json.dumps(data,indent=4),encoding='utf8');temp.replace(self.path)
    def start(self):
        self.thread=threading.Thread(target=self.run,name='visibility',daemon=True);self.thread.start()
    def run(self):
        while not self.stop.is_set():
            try:self.flush()
            except (OSError,ValueError):logging.getLogger(__name__).debug('GlassVR settings busy/unavailable; retrying')
            self.stop.wait(.1)
    def close(self):
        self.update({1:False,2:False});self.stop.set()
        if hasattr(self,'thread'):self.thread.join(1)
        for _ in range(20):
            try:self.flush();return
            except (OSError,ValueError):self.stop.wait(.01)
        logging.getLogger(__name__).warning('Could not disable GlassVR devices on shutdown')
