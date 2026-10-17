# MPBR version 2

UDP39580; Bonjour `_mpbridge._udp.local.`, TXT protocol=MPBR/version=2.
Контроль — JSON protocol/v: hello с nonce, welcome с session, ping/pong/sync.
Endpoint/session/nonce отделяют текущий сеанс. Протокол локальный, без
криптографической аутентификации/шифрования. VHBR/v1 отклоняется;
экспериментальный MPBR/v2 совместим.

Little endian, header `<4sBBHIQdHH4f`, 48 байт: magic, version, hand count,
flags (bit0 estimated intrinsics), sequence uint32, session uint64, capture
host monotonic seconds, width/height, fx/fy/cx/cy.

Рука `<IBbH134fI`, 548 байт: track_id, side (0 unknown/1 left/2 right),
palm heuristic, reserved=0; 21×(normalized x-right,y-down,availability),
21×(world x,y,z metres), camera wrist position3, palm quaternion4 xyzw,
reprojection RMS pixels, pose_valid uint32. World points имеют локальный центр;
camera translation вычисляет телефон. UIKit rotation/mirroring не применяются.

Две руки — 1144 байта, ниже обычного Ethernet MTU с UDP/IP. Значения и длина
проверяются. Sequence wrap учитывается; дубликаты/старые пакеты отклоняются.
Принимается последний кадр, очередь не растёт. Clock sync связывает capture
iPhone с monotonic ПК; устаревшая pose не выводится.

GlassVR loopback: P=25, R=33 (wxyz), I=77, S=201 байт. S кодирует пять curls
в индексах 0/4/8/12/16 и пять splays; драйвер симулирует кости OpenVR.
Это не wire format независимых joint rotations.
