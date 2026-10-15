# Discovery on Wi-Fi, Ethernet and Windows hotspot

Discovery now enumerates every assigned non-loopback IPv4 adapter, including
Windows Mobile Hotspot/ICS (commonly 192.168.137.1), Ethernet, Wi-Fi, VPN and
link-local adapters. Each adapter advertises a separate Bonjour service and
hostname with only its own address. It no longer chooses only the default route.
Adapters are rescanned every five seconds, so enabling hotspot after startup is
supported. UDP listens on 0.0.0.0 by default.

Keep `network.advertise_ip: null` and `network.bind_ip: 0.0.0.0` for automatic
all-interface discovery. An explicit advertise_ip or bind_ip remains a deliberate
single-interface override. This fix is PC-side; existing iOS IPA uses the same
Bonjour protocol and need not be replaced for this change.

Windows may classify Wi-Fi/hotspot as Public. Run
`scripts/allow_local_network.ps1` as Administrator once to allow inbound UDP39570
and mDNS UDP5353 from LocalSubnet on all profiles. These rules do not open the
server to arbitrary Internet addresses. If using a different stream port, adapt
the UDP39570 rule accordingly.

This covers locally reachable IPv4 networks, not arbitrary separated Internet
networks. Bonjour does not cross routers by default; AP isolation, VPN routing
restrictions or filtering multicast still require network configuration. IPv6-only
discovery/streaming is not implemented in the current iOS IPv4 wire transport.
