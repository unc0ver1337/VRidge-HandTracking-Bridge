"""Valve Index tracking origin is different from the SteamVR pointing ray.

Fallbacks come from SteamVR's valve_controller_knu_1_0_{left,right}.json,
components.tip.component_local.rotate_xyz. The running OpenVR component matrix
is preferred; this avoids assuming an Euler convention or installed model version.
"""
import numpy as np
from scipy.spatial.transform import Rotation

INDEX_TIP_XYZ_DEG = {1: (-40., -5., 0.), 2: (-40., 5., 0.)}

def stock_tips():
    return {side:Rotation.from_euler('xyz',angles,degrees=True) for side,angles in INDEX_TIP_XYZ_DEG.items()}

def runtime_tips(openvr):
    result={}
    models=openvr.VRRenderModels()
    for side,name in ((1,'left'),(2,'right')):
        ok,state=models.getComponentState('{indexcontroller}valve_controller_knu_1_0_'+name,
            'tip',openvr.VRControllerState_t(),openvr.RenderModel_ControllerMode_State_t())
        if not ok:continue
        matrix=np.asarray(state.mTrackingToComponentLocal.m,dtype=float)[:,:3]
        if matrix.shape!=(3,3) or not np.isfinite(matrix).all():continue
        if not np.allclose(matrix.T@matrix,np.eye(3),atol=1e-4) or abs(np.linalg.det(matrix)-1)>.001:continue
        result[side]=Rotation.from_matrix(matrix)
    return result
