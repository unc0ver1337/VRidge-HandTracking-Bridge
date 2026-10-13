"""10ms input loop independent of reconstruction and camera packet cadence."""
import threading,time,logging
from collections import deque
from .xinput import XInput,Mapper

class InputManager:
    def __init__(self,glass,xinput_config,mapping):
        self.glass=glass;self.pad=XInput(**xinput_config);self.mapper=Mapper(mapping)
        self.lock=threading.Lock();self.events=deque(maxlen=16);self.buttons={1:{},2:{}}
        self.valid_until={1:0,2:0};self.stop=threading.Event()
    def start(self):
        self.thread=threading.Thread(target=self.run,name='xinput',daemon=True);self.thread.start()
    def tracked(self,side,now):
        with self.lock:self.valid_until[side]=now+.35
    def take(self):
        with self.lock:
            buttons={s:b.copy() for s,b in self.buttons.items()};events=list(self.events);self.events.clear()
        return buttons,events
    def run(self):
        connected=None
        while not self.stop.is_set():
            try:
                pad=self.pad.poll()
                if pad.connected!=connected:
                    connected=pad.connected;logging.getLogger(__name__).info('Xbox 360/XInput %s','connected' if connected else 'not connected; releasing input')
                before=(self.mapper.side,self.mapper.split)
                buttons,events=self.mapper.update(pad);now=time.monotonic()
                if before!=(self.mapper.side,self.mapper.split):logging.getLogger(__name__).info('Button hand=%s sticks=%s','left' if self.mapper.side==1 else 'right','split' if self.mapper.split else 'selected hand')
                with self.lock:
                    self.buttons=buttons;self.events.extend(events)
                    safe={s:(buttons[s] if now<self.valid_until[s] else {}) for s in (1,2)}
                for side in (1,2):self.glass.input_only(side,safe[side])
            except Exception:logging.getLogger(__name__).exception('XInput isolated error')
            self.stop.wait(.01)
    def close(self):
        self.stop.set()
        if hasattr(self,'thread'):self.thread.join(1)
