from types import SimpleNamespace
from unittest.mock import patch
from pc.interfaces import local_ipv4

def test_all_adapters_including_hotspot_vpn_and_link_local():
    adapters=[SimpleNamespace(ips=[SimpleNamespace(ip=ip) for ip in values]) for values in
              [['192.168.10.8','127.0.0.1'],['192.168.137.1'],['10.8.0.2','169.254.1.2'],[('fe80::1',0,0),'0.0.0.0']]]
    with patch('pc.interfaces.ifaddr.get_adapters',return_value=adapters):
        assert set(local_ipv4())=={'192.168.10.8','192.168.137.1','10.8.0.2','169.254.1.2'}
        assert local_ipv4('127.0.0.1')==['127.0.0.1']
        assert local_ipv4(bind_ip='192.168.137.1')==['192.168.137.1']

def test_hotspot_added_and_removed_without_restarting_stream_socket():
    from pc.network import Server
    class Announcement:
        def __init__(self,**kwargs):self.services=[];self.closed=False
        def register_service(self,service):self.services.append(service)
        def unregister_service(self,service):self.services.remove(service)
        def close(self):self.closed=True
    server=Server()
    with patch('zeroconf.Zeroconf',Announcement),patch('pc.network.local_ipv4',return_value=['192.168.10.8']):server.refresh_interfaces()
    wifi=server.announcements['192.168.10.8'][0]
    with patch('zeroconf.Zeroconf',Announcement),patch('pc.network.local_ipv4',return_value=['192.168.10.8','192.168.137.1']):server.refresh_interfaces()
    assert server.announcements['192.168.10.8'][0] is wifi
    hotspot,service=server.announcements['192.168.137.1']
    assert service.parsed_addresses()==['192.168.137.1']
    assert '192-168-137-1' in service.server
    with patch('pc.network.local_ipv4',return_value=['192.168.10.8']):server.refresh_interfaces()
    assert hotspot.closed and not wifi.closed
    server.close();assert wifi.closed
