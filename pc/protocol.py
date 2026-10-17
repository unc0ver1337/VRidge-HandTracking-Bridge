"""Little-endian wire format shared with ios/Network/Wire.h. Max 1144 bytes."""
from dataclasses import dataclass
import struct
import numpy as np

HEADER = struct.Struct('<4sBBHIQdHH4f')
HAND = struct.Struct('<IBbH134fI')
MAGIC = b'MPBR'
VERSION = 2

@dataclass
class Hand:
    track_id: int
    side: int  # 0 unknown, 1 left, 2 right
    palm: int  # 0 unknown, +/-1 heuristic only, never a hard constraint
    points: np.ndarray  # x right, y down, availability (not joint confidence)
    world: np.ndarray = None
    position: np.ndarray = None
    quaternion: np.ndarray = None
    reprojection: float = 0.
    pose_valid: bool = False

@dataclass
class Frame:
    seq: int
    session: int
    capture: float  # iOS monotonic host clock seconds, NOT Unix
    width: int
    height: int
    intrinsics: np.ndarray
    hands: list[Hand]
    flags: int = 0  # bit 0: estimated intrinsics

def encode(f):
    raw=HEADER.pack(MAGIC, VERSION, len(f.hands), f.flags, f.seq, f.session,
                    f.capture, f.width, f.height, *f.intrinsics)
    for h in f.hands:
        if h.world is None or h.position is None or h.quaternion is None:raise ValueError('MP 3D payload required')
        raw+=HAND.pack(h.track_id,h.side,h.palm,0,*np.asarray(h.points).ravel(),*np.asarray(h.world).ravel(),*h.position,*h.quaternion,h.reprojection,int(h.pose_valid))
    decode(raw)  # enforce same validation on producers
    return raw

def decode(raw):
    if len(raw)<HEADER.size: raise ValueError('short header')
    magic,version,n,flags,seq,session,t,w,h,*k=HEADER.unpack_from(raw)
    if magic!=MAGIC or version!=VERSION or n>2 or flags & ~1: raise ValueError('protocol')
    if len(raw)!=HEADER.size+n*HAND.size: raise ValueError('length')
    if not 16<=w<=8192 or not 16<=h<=8192: raise ValueError('dimensions')
    if not np.isfinite([t,*k]).all() or t<0 or min(k[:2])<=0: raise ValueError('camera')
    hands=[]
    for i in range(n):
        ident,side,palm,res,*p=HAND.unpack_from(raw,HEADER.size+i*HAND.size)
        state=p.pop();values=np.array(p)
        p=values[:63].reshape(21,3);world=values[63:126].reshape(21,3)
        position=values[126:129];quat=values[129:133];error=values[133]
        if not np.isfinite(values).all() or np.any(np.abs(world)>1) or np.any(np.abs(position)>5) or state not in (0,1) or error<0:raise ValueError('MP geometry')
        if state and (not .08<=position[2]<=2.5 or abs(np.linalg.norm(quat)-1)>.01 or error>20):raise ValueError('MP pose')
        if side not in (0,1,2) or palm not in (-1,0,1) or res: raise ValueError('hand metadata')
        if not np.isfinite(p).all() or np.any(p<0) or np.any(p>1): raise ValueError('landmarks')
        hands.append(Hand(ident,side,palm,p,world,position,quat,float(error),bool(state)))
    return Frame(seq,session,t,w,h,np.array(k),hands,flags)

class Sequence:
    def __init__(self): self.last=None; self.received=0; self.missing=0; self.rejected=0
    def accept(self,seq):
        if self.last is not None:
            delta=(seq-self.last)&0xffffffff
            if delta==0 or delta>=0x80000000:
                self.rejected+=1
                return False
            self.missing+=delta-1
        self.last=seq; self.received+=1
        return True
    @property
    def loss(self): return self.missing/max(1,self.received+self.missing)
