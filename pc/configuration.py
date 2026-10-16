"""Fresh, camera-derived orientation on each launch; no saved grip profiles."""
from pathlib import Path
import yaml

def load_config(path):
    cfg=yaml.safe_load(Path(path).read_text(encoding='utf8'))
    cfg['space']['grip_rotation_deg']={'1':[0.,0.,0.],'2':[0.,0.,0.]}
    return cfg
