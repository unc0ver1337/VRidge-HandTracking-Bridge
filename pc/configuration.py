"""Load base settings and only saved per-hand orientation corrections."""
import logging
from pathlib import Path
import numpy as np
import yaml

def load_config(path):
    path=Path(path);cfg=yaml.safe_load(path.read_text(encoding='utf8'))
    saved=path.with_name('orientation.local.yaml')
    if saved.exists() and saved.resolve()!=path.resolve():
        try:
            data=yaml.safe_load(saved.read_text(encoding='utf8'))
            corrections=data['space']['grip_rotation_deg']
            checked={}
            for side in ('1','2'):
                value=np.asarray(corrections[side],dtype=float)
                if value.shape!=(3,) or not np.isfinite(value).all():raise ValueError('invalid grip rotation')
                checked[side]=value.tolist()
            cfg['space']['grip_rotation_deg']=checked
            logging.getLogger(__name__).info('Loaded saved grip orientation: %s',saved)
        except (OSError,ValueError,KeyError,TypeError,yaml.YAMLError):
            logging.getLogger(__name__).warning('Saved orientation invalid; using base config',exc_info=True)
    return cfg
