"""Camera-relative pose produced by the phone and decoded for GlassVR."""
from dataclasses import dataclass
import numpy as np

@dataclass
class Estimate:
    position: np.ndarray
    quaternion: np.ndarray  # xyzw
    joints: np.ndarray
    angles: np.ndarray
    pixel_rmse: float
    depth_sigma_m: float  # heuristic uncertainty floor, not measured covariance
    orientation_ambiguous: bool
    solve_ms: float
    palm_normal: np.ndarray
    palm_facing: str
    finger_valid: np.ndarray
    palm_rmse: float
    orientation_held: bool = False
