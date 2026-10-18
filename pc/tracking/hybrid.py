"""Vision palm pose and independent, timestamped Core ML articulation.

Five palm anchors drive planar PnP. Finger tips and neural world geometry never
enter controller pose estimation. Monocular depth uses the configured MCP width.
"""
import time
import cv2
import numpy as np
from scipy.spatial.transform import Rotation
from .pose import Estimate
from .mediapipe import bend

IDS = np.array([0, 5, 9, 13, 17])
PALM = np.array([[0, 0, 0], [.0425, .085, 0], [.012, .095, 0],
                 [-.018, .09, 0], [-.0425, .075, 0]], dtype=np.float64)

class Decoder:
    def __init__(self, palm_width_m=.085, max_reprojection_px=12., max_angular_speed_deg=600.):
        if not .045 <= palm_width_m <= .13: raise ValueError('palm_width_m outside anatomical range')
        self.model = PALM * (palm_width_m / np.linalg.norm(PALM[1] - PALM[4]))
        self.max_error = max_reprojection_px
        self.max_speed = np.deg2rad(max_angular_speed_deg)
        self.previous = {}

    def decode(self, hand, side, frame):
        started = time.perf_counter()
        if not frame.flags & 2: raise ValueError('hybrid Vision frame required')
        points = np.asarray(hand.points, dtype=float)
        if side not in (1, 2) or points.shape != (21, 3): raise ValueError('Vision hand shape')
        if not np.isfinite(points).all() or np.min(points[IDS, 2]) < .35: raise ValueError('Vision palm occluded')
        obj = self.model.copy()
        if side == 1: obj[:, 0] *= -1
        fx, fy, cx, cy = frame.intrinsics
        k = np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.]])
        pixels = np.ascontiguousarray(points[IDS, :2] * [frame.width, frame.height])
        result = cv2.solvePnPGeneric(obj, pixels, k, None, flags=cv2.SOLVEPNP_IPPE)
        previous = self.previous.get(side)
        recent = previous is not None and 0 < frame.capture - previous[0] < .35
        candidates = []
        for rvec, tvec in zip(result[1], result[2]):
            rot = Rotation.from_rotvec(rvec.ravel()); pos = tvec.ravel()
            xyz = rot.apply(obj) + pos
            if not np.isfinite(xyz).all() or np.min(xyz[:, 2]) < .08 or not .08 <= pos[2] <= 2.5: continue
            projected = cv2.projectPoints(obj, rvec, tvec, k, None)[0].reshape(-1, 2)
            error = float(np.sqrt(np.mean(np.sum((projected-pixels)**2, axis=1))))
            if error > self.max_error: continue
            angle = (rot * previous[2].inv()).magnitude() if recent else 0.
            # A 180-degree branch jump cannot be a measured 30 FPS motion.
            # Reprojection remains primary; continuity breaks near-equal solutions.
            allowed = self.max_speed * (frame.capture-previous[0]) + np.deg2rad(8) if recent else np.pi
            if recent and angle > allowed: continue
            score = error + (2. * angle if recent else 0.)
            candidates.append((score, error, pos, rot))
        held = False
        if not candidates:
            # Never extrapolate stale pose after loss. A short ambiguity may hold
            # orientation only; translation still needs a valid geometric solution.
            raise ValueError('Vision pose ambiguous or reprojection rejected')
        candidates.sort(key=lambda v: v[0])
        _, error, pos, rot = candidates[0]
        ambiguity = len(candidates) > 1 and abs(candidates[1][1]-error) < 1.
        a,b = pixels[1]-pixels[0],pixels[4]-pixels[0]
        area = abs(a[0]*b[1]-a[1]*b[0])
        extent = np.linalg.norm(pixels[1]-pixels[4]) * np.linalg.norm(pixels[2]-pixels[0])
        edge = extent < 1 or area/max(extent, 1) < .08
        if recent and edge:
            rot = previous[2]; held = True
        q = rot.as_quat()
        if recent and np.dot(q, previous[2].as_quat()) < 0: q = -q
        self.previous[side] = (frame.capture, pos.copy(), rot)
        angles = np.zeros((5, 4)); valid = np.zeros(5, dtype=bool)
        world = np.asarray(hand.world)
        age = frame.capture - hand.finger_capture
        if hand.finger_capture > 0 and -.01 <= age <= .25 and world.shape == (21, 3) and np.isfinite(world).all():
            # Articulation gets its OWN palm basis from the SAME neural sample.
            # Subtracting a Vision rotation from older neural joints smears fingers.
            x = (world[5]-world[17]) * (-1 if side == 1 else 1)
            y = world[9]-world[0]
            if np.linalg.norm(x) > .005 and np.linalg.norm(y) > .005:
                x /= np.linalg.norm(x); y -= x*np.dot(x, y)
                if np.linalg.norm(y) > .005:
                    y /= np.linalg.norm(y); z = np.cross(x, y)
                    local = (world-world[0]) @ np.column_stack((x,y,z))
                    if side == 1: local[:,0] *= -1
                    for digit in range(5):
                        a,b,c = np.diff(local[1+4*digit:5+4*digit], axis=0)
                        if min(map(np.linalg.norm, (a,b,c))) < 1e-5: continue
                        valid[digit] = True
                        angles[digit] = [np.clip(np.arctan2(a[0],a[1])-(.85 if digit==0 else 0),-.61,.61),
                            np.clip(np.arctan2(a[2],np.hypot(a[0],a[1])),-.15,1.66),
                            np.clip(bend(a,b),0,1.92),np.clip(bend(b,c),0,1.48)]
        normal = rot.apply([0,0,1])
        return Estimate(pos,q,rot.apply(obj)+pos,angles,error,
            max(.15*pos[2], error/max(fx,fy)*pos[2]),bool(ambiguity or edge),
            (time.perf_counter()-started)*1000,normal,'uncertain' if edge else ('toward' if normal[2]<0 else 'away'),
            valid,error,held)
