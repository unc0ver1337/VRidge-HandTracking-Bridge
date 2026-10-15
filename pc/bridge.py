"""Run: python -m pc.bridge --config pc/config.yaml"""
import argparse,logging,time,json,os
from logging.handlers import RotatingFileHandler
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
from .glassvr.visibility import DevicePresence

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--config',default='pc/config.yaml'); parser.add_argument('--log',default='bridge.log');parser.add_argument('--duration',type=float,default=0,help='Optional diagnostic runtime in seconds'); args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(name)s %(message)s',handlers=[logging.StreamHandler(),RotatingFileHandler(args.log,maxBytes=8*1024*1024,backupCount=3,encoding='utf8')])
    log=logging.getLogger('bridge'); cfg=yaml.safe_load(Path(args.config).read_text())
    driver_settings=Path(os.environ.get('APPDATA',''))/'glassvr/settings.json'
    if driver_settings.exists():
        installed=json.loads(driver_settings.read_text(encoding='utf8'))
        for side,key in (('left','cl port'),('right','cr port')):
            port=installed.get(key)
            if isinstance(port,int) and 1<=port<=65535:
                if cfg['glassvr'][side+'_port']!=port:log.warning('Aligning %s UDP port with installed GlassVR: %d',side,port)
                cfg['glassvr'][side+'_port']=port
    log.info('GlassVR UDP ports: left=%d right=%d',cfg['glassvr']['left_port'],cfg['glassvr']['right_port'])
    server=Server(**cfg['network']); solver=Solver(**cfg['reconstruction']); identity=Identity()
    filters={s:PoseFilter(**cfg['filter']) for s in (1,2)}; glass=GlassVR(**cfg['glassvr']); space=Space(cfg['space'])
    presence=DevicePresence();inputs=InputManager(glass,cfg['xinput'],cfg['mapping'],presence); current={}; n=0; solved_ms=[]; latencies=[]; report=time.monotonic(); started=False
    active_session=None; quality={};reasons={}; latest_orientation={}
    try:
        server.start(); started=True; space.start();presence.start();inputs.start();run_start=time.monotonic()
        while True:
            now=time.monotonic()
            if args.duration>0 and now-run_start>=args.duration:break
            buttons,events=inputs.take()
            centering='center_orientation' in events
            if events:
                for event in events:
                    if event=='center_orientation':
                        centered=[]
                        for side,(quaternion,stamp) in latest_orientation.items():
                            if now-stamp<.35:
                                space.center_orientation(quaternion,side);centered.append(side)
                    elif event=='center_orientation_release':
                        if latest_orientation:
                            saved=Path(args.config).with_name('orientation.local.yaml')
                            saved.write_text(yaml.safe_dump(cfg,sort_keys=False),encoding='utf8')
                            log.info('Continuous orientation centering released; saved %s',saved)
                    elif event=='calibrate' and current:
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
                if f.session!=active_session:
                    active_session=f.session;solver.previous.clear();identity=Identity();latest_orientation.clear()
                if cfg.get('camera_intrinsics') is not None: f.intrinsics=np.asarray(cfg['camera_intrinsics'],float)
                for side,hand in identity.update(f.hands,f.capture).items():
                    current[side]=(side,hand,f)
                    try:
                        pose=solver.solve(hand,f,side)
                        if centering:space.center_orientation(pose.quaternion,side)
                        # Transform using head pose at CAPTURE, filter in WORLD coordinates.
                        p,q=space.transform(pose.position,pose.quaternion,capture_pc,side)
                        target_q=q.copy();p,q=filters[side].update(p,q,capture_pc)
                        if centering:q=target_q;filters[side].q=q.copy()
                        # Drop results that spent too long optimizing; never render a
                        # stale cold-start result or overwrite fresh XInput state.
                        if time.monotonic()-capture_pc>.2:raise ValueError('solve exceeded pose freshness budget')
                        glass.send(side,p,q,{},pose.angles,include_input=False); inputs.tracked(side,time.monotonic())
                        latest_orientation[side]=(pose.quaternion.copy(),time.monotonic())
                        solved_ms.append(pose.solve_ms)
                        quality[side]={'reprojection_px':round(pose.pixel_rmse,2),'depth_sigma_m':round(pose.depth_sigma_m,3),'palm':pose.palm_facing,'orientation_ambiguous':pose.orientation_ambiguous}
                    except ValueError as error:
                        message=str(error);reasons[message]=reasons.get(message,0)+1
                    except Exception: log.exception('isolated hand processing failure')
                n+=1; latencies.append((time.monotonic()-capture_pc)*1000)
            if now-report>=2:
                active=bool(server.peer and now-server.last_seen<server.timeout)
                log.info('phone=%s fps=%.1f capture-to-output=%.1fms (+/- clock %.1fms) reconstruction=%.1fms/hand loss=%.2f%% stale=%d invalid=%d replaced=%d', 'connected' if active else 'waiting',n/(now-report),np.mean(latencies) if latencies else 0,server.rtt*500,np.mean(solved_ms) if solved_ms else 0,server.seq.loss*100,server.clock_rejected,server.invalid,server.replaced)
                if quality or reasons:log.info('hand quality=%s rejected=%s',quality,reasons)
                quality.clear();reasons.clear()
                n=0; solved_ms.clear(); latencies.clear(); report=now
            time.sleep(.001)
    except KeyboardInterrupt: log.info('Stopping; releasing controller input')
    finally:
        inputs.close();presence.close();glass.close(); space.close()
        server.close()

if __name__=='__main__': main()
