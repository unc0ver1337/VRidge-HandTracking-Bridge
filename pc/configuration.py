"""Load network/input/geometry configuration. Grip can be re-centered separately."""
from pathlib import Path
import yaml

def load_config(path):
    cfg=yaml.safe_load(Path(path).read_text(encoding='utf8'))
    cfg['space'].pop('grip_rotation_deg',None) # Ignore obsolete local calibration.
    return cfg
