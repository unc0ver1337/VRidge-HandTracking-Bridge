# VHBR protocol v1

Bonjour type `_vhbridge._udp.local.`, human-readable instance `GlassVR iPhone Bridge`. TXT `protocol=VHBR`, `version=1`, random instance UUID. Stream/control UDP 39570; GlassVR ports are separate loopback endpoints 9001/9002.

Control JSON always has `protocol: VHBR`, `v: 1`, `type`. iOS sends `hello {nonce: UUID, device: name}`. Server replies `welcome {nonce, session: random 52-bit positive integer}`. Only one source IP+port may hold the active 3-second lease. Session fits JSON/JavaScript exact integer range. This avoids accidental unrelated peers, **not malicious LAN spoofing**. No authentication, encryption or confidentiality guarantee: trusted private LAN only.

Every 0.5 s iOS sends `ping {session,t0}`. Server records PC monotonic `s1` at receipt and `s2` at send; replies `pong {session,t0,s1,s2}`. iOS records host clock `t3` and sends `sync {session,t0,t3,s1,s2}`. Server uses:

```text
offset PC-minus-iOS = ((s1-t0)+(s2-t3))/2
RTT = (t3-t0)-(s2-s1)
capture_pc = capture_ios + offset
```

Minimum observed RTT in a sliding 60-second window selects the current offset, refreshing oscillator drift without following every Wi-Fi delay spike. Reported ±RTT/2 bounds path asymmetry only approximately; no absolute one-way latency is known. Clock sync must succeed before accepting frames. Packets >200ms old or >30ms in the future are dropped. Captures use AVFoundation sample presentation timestamp converted to the host clock, not inference completion or wall clock.

Binary little-endian header, 48 bytes (`<4sBBHIQdHH4f`):

| Field | Type | Meaning |
|---|---|---|
| magic | 4 bytes | ASCII VHBR |
| version | uint8 | 1 |
| count | uint8 | 0–2 hands |
| flags | uint16 | bit0 estimated K; others invalid |
| sequence | uint32 | modulo 2³² |
| session | uint64 | handshake session |
| capture | float64 | iOS host clock seconds |
| width,height | uint16 each | actual Vision image size |
| fx,fy,cx,cy | float32 each | pixel intrinsics of that same image |

Each hand, 260 bytes (`<IBbH63f`):

| Field | Type | Meaning |
|---|---|---|
| identity | uint32 | semantic observation hint; PC performs temporal assignment |
| side | uint8 | 0 unknown, 1 left, 2 right |
| palm | int8 | -1 toward camera, +1 away, 0 uncertain; weak winding heuristic |
| reserved | uint16 | must be zero |
| landmarks | 21 × 3 float32 | normalized x right, y down, confidence, all finite [0,1] |

Landmark order: wrist; thumb CMC/MP/IP/tip; index MCP/PIP/DIP/tip; middle; ring; little. Missing joints have confidence zero. Camera remains native sensor orientation and unmirrored independent of UI rotation; no silent image rotation is introduced. Max datagram 48+2×260=568 bytes. Transport sends no RGB images.

Accept sequence when `(seq-last)&0xffffffff` is in `[1,0x7fffffff]`. Duplicate/old packets are rejected; forward gaps count missing packets. Latest-frame replacement bounds processing backlog. Connection reset creates a new sequence/session state. Identity and solver history reset on session change; world pose filtering maintains bounded reacquisition.
