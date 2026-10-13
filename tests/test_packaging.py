import struct,pytest
from scripts.package_ipa import inject,LOAD_PATH

def macho(encrypted=0,slack=True):
    # One section at offset 4096 with a recognizable nonzero body.
    header=struct.pack('<8I',0xfeedfacf,0x100000c,0,2,2,176,0,0)
    segment=struct.pack('<II16s4Q4I',0x19,152,b'__TEXT',0,8192,0,8192,7,5,1,0)
    section=struct.pack('<16s16sQQ8I',b'__text',b'__TEXT',4096,16,4096,2,0,0,0,0,0,0)
    crypt=struct.pack('<6I',0x2c,24,4096,16,encrypted,0)
    body=(header+segment+section+crypt).ljust(4096,b'\0')+b'CODE_NOT_CHANGED'
    if not slack:body=body[:208]+b'X'*500+body[708:]
    return body

def test_inject_preserves_code_and_adds_load_command():
    original=macho();result=inject(original)
    assert result[4096:]==original[4096:];assert LOAD_PATH.encode() in result
    assert struct.unpack_from('<I',result,16)[0]==3
    with pytest.raises(ValueError):inject(result)

def test_inject_refuses_encryption_and_occupied_slack():
    with pytest.raises(ValueError):inject(macho(1))
    with pytest.raises(ValueError):inject(macho(slack=False))
