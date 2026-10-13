"""Little-endian wire format shared with ios/Network/Wire.h. Max 568 bytes."""
from dataclasses import dataclass
import struct
import numpy as np

HEADER = struct.Struct('<4sBBHIQdHH4f')
HAND = struct.Struct('<IBbH63f')
MAGIC = b'VHBR'
VERSION = 1

@dataclass
class Hand:
    track_id: int
    side: int  # 0 unknown, 1 left, 2 right
    palm: int  # 0 unknown, +/-1 heuristic only, never a hard constraint
    points: np.ndarray  # x right, y down, confidence

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
        raw+=HAND.pack(h.track_id,h.side,h.palm,0,*np.asarray(h.points).ravel())
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
        p=np.array(p).reshape(21,3)
        if side not in (0,1,2) or palm not in (-1,0,1) or res: raise ValueError('hand metadata')
        if not np.isfinite(p).all() or np.any(p<0) or np.any(p>1): raise ValueError('landmarks')
        hands.append(Hand(ident,side,palm,p))
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
