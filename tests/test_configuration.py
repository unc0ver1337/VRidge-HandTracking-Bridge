import yaml
from pc.configuration import load_config

def test_load_saved_grip_without_overwriting_network(tmp_path):
    p=tmp_path/'config.yaml';p.write_text(yaml.safe_dump({'network':{'port':1234},'space':{'grip_rotation_deg':{'1':[0,0,0],'2':[0,0,0]}}}))
    saved=tmp_path/'orientation.local.yaml';saved.write_text(yaml.safe_dump({'network':{'port':9999},'space':{'grip_rotation_deg':{'1':[1,2,3],'2':[4,5,6]}}}))
    cfg=load_config(p);assert cfg['network']['port']==1234;assert cfg['space']['grip_rotation_deg']['1']==[1,2,3]
    saved.write_text('broken: [')
    assert load_config(p)['space']['grip_rotation_deg']['1']==[0,0,0]
