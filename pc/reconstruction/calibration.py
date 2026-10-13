"""Extrinsics fitting and camera checkerboard calibration; no invented world pose."""
import numpy as np
from scipy.spatial.transform import Rotation

def rigid_alignment(camera_points,world_points):
    a=np.asarray(camera_points,dtype=float); b=np.asarray(world_points,dtype=float)
    if a.shape!=b.shape or a.ndim!=2 or a.shape[1]!=3 or len(a)<3: raise ValueError('need >=3 paired 3D points')
    ac=a-a.mean(0); bc=b-b.mean(0)
    if np.linalg.matrix_rank(ac)<2: raise ValueError('collinear calibration')
    u,s,vt=np.linalg.svd(ac.T@bc); r=vt.T@u.T
    if np.linalg.det(r)<0: vt[-1]*=-1; r=vt.T@u.T
    t=b.mean(0)-r@a.mean(0)
    return r,t,float(np.sqrt(np.mean(np.sum((a@r.T+t-b)**2,axis=1))))

def checkerboard(images,columns,rows,square_m):
    import cv2 # optional offline dependency
    obj=np.zeros((columns*rows,3),np.float32); obj[:,:2]=np.mgrid[:columns,:rows].T.reshape(-1,2)*square_m
    objects=[]; corners=[]; size=None
    for image in images:
        gray=cv2.imread(str(image),cv2.IMREAD_GRAYSCALE)
        if gray is None: raise ValueError('unreadable calibration image')
        if size and size!=gray.shape[::-1]: raise ValueError('mixed image resolutions')
        size=gray.shape[::-1]
        ok,pts=cv2.findChessboardCornersSB(gray,(columns,rows))
        if ok: objects.append(obj.copy()); corners.append(pts)
    if len(objects)<10: raise ValueError('need >=10 diverse checkerboard views from tracking format')
    rms,k,d,_,_=cv2.calibrateCamera(objects,corners,size,None,None)
    return {'rms_pixels':float(rms),'resolution':list(size),'intrinsics':[float(k[0,0]),float(k[1,1]),float(k[0,2]),float(k[1,2])],'distortion':d.ravel()[:5].tolist()}
