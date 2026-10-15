import ctypes,sys
from dataclasses import dataclass,field
import numpy as np

MASK={'dpad_up':1,'dpad_down':2,'dpad_left':4,'dpad_right':8,'start':16,'back':32,'ls':64,'rs':128,'lb':256,'rb':512,'a':4096,'b':8192,'x':16384,'y':32768}
class Gamepad(ctypes.Structure):
    _fields_=[('buttons',ctypes.c_ushort),('lt',ctypes.c_ubyte),('rt',ctypes.c_ubyte),('lx',ctypes.c_short),('ly',ctypes.c_short),('rx',ctypes.c_short),('ry',ctypes.c_short)]
class State(ctypes.Structure): _fields_=[('packet',ctypes.c_uint32),('pad',Gamepad)]

@dataclass
class Input:
    connected: bool=False
    buttons: set=field(default_factory=set)
    lt: float=0.
    rt: float=0.
    left: tuple=(0.,0.)
    right: tuple=(0.,0.)

def deadzone(x,y,zone):
    v=np.array([x,y],float); length=np.linalg.norm(v)
    if length<=zone: return (0.,0.)
    return tuple(v/length*min(1.,(length-zone)/(1-zone)))

class XInput:
    def __init__(self,index=0,deadzone_value=.18,trigger_deadzone=.05):
        self.index=index; self.zone=deadzone_value; self.trigger_zone=trigger_deadzone; self.dll=None
        if sys.platform=='win32':
            for name in ('xinput1_4.dll','xinput1_3.dll','xinput9_1_0.dll'):
                try: self.dll=ctypes.WinDLL(name); break
                except OSError: continue
            if self.dll:
                self.dll.XInputGetState.argtypes=[ctypes.c_uint32,ctypes.POINTER(State)]
                self.dll.XInputGetState.restype=ctypes.c_uint32
    def poll(self):
        s=State()
        if not self.dll or self.dll.XInputGetState(self.index,ctypes.byref(s))!=0: return Input()
        p=s.pad
        trigger=lambda v:max(0.,(v/255-self.trigger_zone)/(1-self.trigger_zone))
        return Input(True,{k for k,m in MASK.items() if p.buttons&m},trigger(p.lt),trigger(p.rt),deadzone(p.lx/32768,p.ly/32768,self.zone),deadzone(p.rx/32768,p.ry/32768,self.zone))

class Mapper:
    def __init__(self,mapping): self.mapping=mapping; self.side=2; self.last=set(); self.split=True
    def update(self,pad):
        m=self.mapping; events=[]; out={1:{},2:{}}
        down=pad.buttons-self.last; self.last=pad.buttons.copy()
        if not pad.connected: self.last=set(); return out,events
        if m.get('layout')=='dual':
            for side,prefix,stick in ((1,'left',pad.left),(2,'right',pad.right)):
                b=out[side]
                b['trigger']=float(getattr(pad,m[prefix+'_trigger']))
                b['trigger_btn']=b['trigger']>.8
                b['grip_pull']=float(m[prefix+'_grip'] in pad.buttons)
                b['grip_force']=b['grip_pull']
                b['b']=m[prefix+'_menu'] in pad.buttons
                b['system']=m[prefix+'_system'] in pad.buttons
                b['joy_btn']=m[prefix+'_stick_click'] in pad.buttons
                b['joy_x'],b['joy_y']=stick
                for key in ('b','system'):b[key+'_cap']=b[key]
                b['joy_cap']=b['joy_btn'] or any(abs(v)>.01 for v in stick)
                b['trigger_cap']=b['trigger']>.01;b['grip_cap']=b['grip_pull']>.01
            return out,events
        if m['select_left'] in pad.buttons: self.side=1
        if m['select_right'] in pad.buttons: self.side=2
        if m['mode'] in down: self.split=not self.split
        for action in ('calibrate','recenter'):
            if m[action] in down: events.append(action)
        b=out[self.side]
        for action in ('a','b','joy_btn','system'):
            b[action]=m.get(action) in pad.buttons
        for action in ('trigger','grip_pull'):
            source=m[action]; b[action]=float(getattr(pad,source)) if source in ('lt','rt') else float(source in pad.buttons)
        b['grip_force']=b['grip_pull']; b['trigger_btn']=b['trigger']>.8
        for key in ('a','b','system'): b[key+'_cap']=b[key]
        b['joy_cap']=b['joy_btn']; b['trigger_cap']=b['trigger']>.01; b['grip_cap']=b['grip_pull']>.01
        if self.split:
            out[1]['joy_x'],out[1]['joy_y']=pad.left
            out[2]['joy_x'],out[2]['joy_y']=pad.right
        else: b['joy_x'],b['joy_y']=pad.left
        return out,events
