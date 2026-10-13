import argparse,json
from pathlib import Path
from pc.reconstruction.calibration import checkerboard
p=argparse.ArgumentParser();p.add_argument('images',nargs='+');p.add_argument('--columns',type=int,required=True);p.add_argument('--rows',type=int,required=True);p.add_argument('--square-m',type=float,required=True);p.add_argument('--output',default='calibration-camera.json')
a=p.parse_args(); result=checkerboard(a.images,a.columns,a.rows,a.square_m);Path(a.output).write_text(json.dumps(result,indent=2)); print(result)
