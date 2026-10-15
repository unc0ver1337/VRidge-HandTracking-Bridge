import ipaddress
import ifaddr

def local_ipv4(override=None,bind_ip='0.0.0.0'):
    if override:return [str(ipaddress.IPv4Address(override))]
    if bind_ip!='0.0.0.0':return [str(ipaddress.IPv4Address(bind_ip))]
    addresses=set()
    for adapter in ifaddr.get_adapters():
        for entry in adapter.ips:
            if not isinstance(entry.ip,str):continue
            ip=ipaddress.ip_address(entry.ip)
            if ip.version==4 and not ip.is_loopback and not ip.is_unspecified and not ip.is_multicast:
                addresses.add(str(ip))
    return sorted(addresses,key=lambda ip:(ipaddress.ip_address(ip).is_link_local,ip))
