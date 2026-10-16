import numpy as np
from pc.glassvr.adapter import GlassVR,packets,input_packet
from pc.tracking.filter import PoseFilter

def test_input_only_matches_full_wire_packet():
    b={'a':True,'trigger':1.5,'joy_x':-3}
    assert input_packet(b)==packets([0,0,0],[0,0,0,1],b,np.zeros((5,4)))[2]

def test_fingers_use_capture_time_and_ignore_old_samples():
    class Sink:
        def __init__(self):self.data=[]
        def sendto(self,data,dest):self.data.append(data)
    a=GlassVR();a.sock.close();a.sock=Sink()
    a.send(1,[0,0,0],[0,0,0,1],{},np.zeros((5,4)),sample_time=10)
    a.send(1,[0,0,0],[0,0,0,1],{},np.ones((5,4))*.5,sample_time=10+1/30)
    old=a.fingers[1][2].copy();n=len(a.sock.data)
    a.send(1,[0,0,0],[0,0,0,1],{},np.ones((5,4)),sample_time=9)
    np.testing.assert_array_equal(a.fingers[1][2],old);assert len(a.sock.data)==n
    assert 2 not in a.fingers

def test_no_prediction_while_recovering():
    a=PoseFilter(prediction_ms=30);a.update([0,0,0],[0,0,0,1],0)
    a.update([1,0,0],[0,0,0,1],1)
    p,_=a.update([1.02,0,0],[0,0,0,1],1+1/30)
    assert a.recovering;np.testing.assert_array_equal(p,a.p)
