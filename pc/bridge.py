"""Run: python -m pc.bridge --config pc/config.yaml"""
import argparse,logging,time
from pathlib import Path
import numpy as np
import yaml
from .network import Server
from .tracking.identity import Identity
from .tracking.filter import PoseFilter
from .reconstruction.solver import Solver
from .reconstruction.model import rays
from .controller.manager import InputManager
from .glassvr.adapter import GlassVR
from .glassvr.space import Space

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',default='pc/config.yaml'); parser.add_argument('--log',default='bridge.log'); args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s',handlers=[logging.StreamHandler(),logging.FileHandler(args.log,encoding='utf8')])
    log=logging.getLogger('bridge'); cfg=yaml.safe_load(Path(args.config).read_text())
    server=Server(**cfg['network']); solver=Solver(**cfg['reconstruction']); identity=Identity()
    filters={s:PoseFilter(**cfg['filter']) for s in (1,2)}; glass=GlassVR(**cfg['glassvr']); space=Space(cfg['space'])
    inputs=InputManager(glass,cfg['xinput'],cfg['mapping']); current={}; n=0; solved_ms=[]; latencies=[]; report=time.monotonic(); started=False
    try:
        server.start(); started=True; space.start();inputs.start()
        while True:
            now=time.monotonic()
            buttons,events=inputs.take()
            if events:
                for event in events:
                    if event=='calibrate' and current:
                        side,h,f=next(iter(current.values())); uv=h.points[:,:2]*[f.width,f.height]
                        rr=rays(uv,f.intrinsics,solver.distortion)
                        width=np.linalg.norm(rr[5]-rr[17])*cfg['calibration_distance_m']
                        if .045<=width<=.13:
                            cfg['reconstruction']['palm_width_m']=float(width); solver=Solver(**cfg['reconstruction'])
                            saved=Path(args.config).with_name('calibration.local.yaml'); saved.write_text(yaml.safe_dump(cfg),encoding='utf8')
                            log.info('Personal palm width %.4fm saved %s; assumes frontal palm at measured distance',width,saved)
                        else: log.warning('Calibration rejected; frontal palm and measured distance required')
                    elif event=='recenter':
                        # Camera/HMD mount is a physical extrinsic. Recenter only temporal
                        # estimates; SteamVR dashboard owns universe recentering.
                        solver.previous.clear(); identity=Identity(); filters={s:PoseFilter(**cfg['filter']) for s in (1,2)}
                        log.info('Temporal state reset; use SteamVR recenter for the tracking universe')
            item=server.take()
            if item:
                f,capture_pc,received=item; current={}
                if cfg.get('camera_intrinsics') is not None: f.intrinsics=np.asarray(cfg['camera_intrinsics'],float)
                for side,hand in identity.update(f.hands,f.capture).items():
                    current[side]=(side,hand,f)
                    try:
                        pose=solver.solve(hand,f,side)
                        # Transform using head pose at CAPTURE, filter in WORLD coordinates.
                        p,q=space.transform(pose.position,pose.quaternion,capture_pc,side)
                        p,q=filters[side].update(p,q,capture_pc)
                        # Drop results that spent too long optimizing; never render a
                        # stale cold-start result or overwrite fresh XInput state.
                        if time.monotonic()-capture_pc>.2:raise ValueError('solve exceeded pose freshness budget')
                        glass.send(side,p,q,{},pose.angles,include_input=False); inputs.tracked(side,time.monotonic())
                        solved_ms.append(pose.solve_ms)
                    except ValueError as error: log.debug('hand %s: %s',side,error)
                    except Exception: log.exception('isolated hand processing failure')
                n+=1; latencies.append((time.monotonic()-capture_pc)*1000)
            if now-report>=2:
                active=bool(server.peer and now-server.last_seen<server.timeout)
                log.info('phone=%s fps=%.1f capture-to-output=%.1fms (+/- clock %.1fms) reconstruction=%.1fms/hand loss=%.2f%% stale=%d invalid=%d replaced=%d', 'connected' if active else 'waiting',n/(now-report),np.mean(latencies) if latencies else 0,server.rtt*500,np.mean(solved_ms) if solved_ms else 0,server.seq.loss*100,server.clock_rejected,server.invalid,server.replaced)
                n=0; solved_ms.clear(); latencies.clear(); report=now
            time.sleep(.001)
    except KeyboardInterrupt: log.info('Stopping; releasing controller input')
    finally:
        inputs.close();glass.close(); space.close()
        if started: server.close()

if __name__=='__main__': main()
