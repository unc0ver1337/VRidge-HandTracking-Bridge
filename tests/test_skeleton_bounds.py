import struct
import numpy as np
from pc.glassvr.adapter import packets

def test_skeleton_values_respect_glassvr_contract():
    for sign in (-1,1):
        angles=np.full((5,4),sign*100.)
        data=struct.unpack('<c25d',packets([0,0,0],[0,0,0,1],{},angles)[3])
        assert all(0<=x<=1 for x in data[1:21])
        assert all(-1<=x<=1 for x in data[21:])
