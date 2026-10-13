import numpy as np,pytest
from pc.protocol import *
from pc.network import Server

def fixture_frame():
    return Frame(1,5,100.,640,480,np.array([400,400,320,240]),[Hand(1,1,0,np.full((21,3),.5)),Hand(2,2,0,np.full((21,3),.6))])

def test_roundtrip_and_mtu():
    f=fixture_frame(); raw=encode(f); assert len(raw)==568
    g=decode(raw); assert g.seq==f.seq and g.session==5
    np.testing.assert_allclose(g.hands[1].points,f.hands[1].points)

@pytest.mark.parametrize('delta',[-1,1,300])
def test_malformed_length(delta):
    raw=encode(fixture_frame()); raw=raw[:delta] if delta<0 else raw+b'x'*delta
    with pytest.raises(ValueError): decode(raw)

@pytest.mark.parametrize('bad',[float('nan'),float('inf'),-0.1,1.1])
def test_bad_landmarks(bad):
    f=fixture_frame(); f.hands[0].points[0,0]=bad
    with pytest.raises(ValueError): encode(f)

def test_sequence_wrap_loss_reorder():
    s=Sequence(); assert s.accept(0xfffffffe);assert s.accept(0);assert s.missing==1
    assert not s.accept(0xffffffff); assert not s.accept(0);assert s.accept(1)
    assert s.rejected==2

def test_network_session_age_and_latest_only():
    s=Server();s.peer=('127.0.0.1',12);s.session=5;s.offset=10
    f=fixture_frame(); raw=encode(f)
    s.ingest(raw,('127.0.0.1',99),110.01); assert s.take() is None
    s.ingest(raw,s.peer,110.01); assert s.take()[0].seq==1
    s.ingest(raw,s.peer,110.02); assert s.take() is None
    f.seq=2;s.ingest(encode(f),s.peer,111); assert s.clock_rejected==1
    f.capture=101;s.ingest(encode(f),s.peer,111.01)
    f.seq=3;s.ingest(encode(f),s.peer,111.02); assert s.replaced==1;assert s.take()[0].seq==3

def test_handshake_and_clock_without_hardware():
    s=Server(); sent=[];s.send=lambda o,a:sent.append(o)
    addr=('10.0.0.2',1234);base={'protocol':'VHBR','v':1}
    s.control(base|{'type':'hello','nonce':'a'*32,'device':'test'},addr,100)
    assert sent[-1]['nonce']=='a'*32
    session=s.session;s.control(base|{'type':'sync','session':session,'t0':90.,'t3':90.02,'s1':100.009,'s2':100.011},addr,100.021)
    assert abs(s.offset-10)<1e-6;assert abs(s.rtt-.018)<1e-6
    s.control(base|{'type':'hello','nonce':'b'*32},('10.0.0.3',1234),100.1)
    assert s.peer==addr and s.session==session

def test_clock_refresh_window_prevents_permanent_old_offset():
    s=Server();s.peer=('10.0.0.2',5);s.session=7;addr=s.peer
    base={'protocol':'VHBR','v':1,'type':'sync','session':7}
    s.control(base|{'t0':90.,'t3':90.01,'s1':100.004,'s2':100.006},addr,100.01)
    assert abs(s.offset-10)<1e-8
    s.control(base|{'t0':151.,'t3':151.02,'s1':161.011,'s2':161.013},addr,161.03)
    assert abs(s.offset-10.002)<1e-8

def test_startup_failure_cleanup_without_equipment():
    s=Server();s.close() # idempotent before resources are allocated
    s.close()
