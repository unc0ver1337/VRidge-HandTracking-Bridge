"""Compare production C++ geometry/crops against pinned upstream Python."""
import ctypes,importlib.util,json,subprocess
from pathlib import Path
import cv2,numpy as np

root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('reference',root/'ios/assets/reference/pipeline.py')
ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
library=root/'ios/build/coreml_math_test.dylib'
subprocess.run(['clang++','-std=c++17','-O2','-ffp-contract=off','-dynamiclib',str(root/'tests/coreml_math_api.cpp'),'-o',str(library)],check=True)
api=ctypes.CDLL(str(library));ptr=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS');integer=ctypes.c_int
api.native_anchors.argtypes=[ptr];api.native_next.argtypes=[ptr,integer,integer,ptr]
api.native_project.argtypes=[ptr,ptr,ctypes.c_float,ptr,ptr]
api.native_decode.argtypes=[ptr,ptr,integer,integer,ptr];api.native_decode.restype=integer
api.native_crop.argtypes=[np.ctypeslib.ndpointer(dtype=np.uint8,flags='C_CONTIGUOUS'),integer,integer,integer,ptr,integer,integer,ptr]
rng=np.random.default_rng(173);aa=np.empty((2016,2),np.float32);api.native_anchors(aa)
np.testing.assert_allclose(aa,ref.generate_anchors()[:,:2],atol=1e-7)
for _ in range(100):
    lm=rng.uniform(.2,.8,(21,3)).astype(np.float32);out=np.empty(5,np.float32)
    api.native_next(lm,640,480,out);np.testing.assert_allclose(out,ref.rect_from_landmarks(lm,640,480),atol=3e-6)
    r=np.array([.4,.6,.5,.5*640/480,rng.uniform(-3,3)],np.float32)
    raw=rng.uniform(0,224,(21,3)).astype(np.float32);world=rng.normal(0,.03,(21,3)).astype(np.float32);projected=np.empty(126,np.float32)
    api.native_project(raw,world,.8,r,projected);c,s=np.float32(np.cos(r[4])),np.float32(np.sin(r[4]))
    x,y=raw[:,0]/224-.5,raw[:,1]/224-.5
    expected=np.stack([(c*x-s*y)*r[2]+r[0],(s*x+c*y)*r[3]+r[1],raw[:,2]/224/.4*r[2]],axis=1)
    np.testing.assert_allclose(projected[:63].reshape(21,3),expected,atol=1e-6)
    expected=np.stack([c*world[:,0]-s*world[:,1],s*world[:,0]+c*world[:,1],world[:,2]],axis=1)
    np.testing.assert_allclose(projected[63:].reshape(21,3),expected,atol=1e-7)
boxes=np.zeros((2016,18),np.float32);scores=np.full(2016,-100,np.float32)
for index in [44,45,1100,1101]:
    boxes[index]=[0,0,25,30,0,10,0,0,0,-10,0,0,0,0,0,0,0,0];scores[index]=5
dets=ref.weighted_nms(ref.decode_detections(boxes,scores[:,None],ref.generate_anchors()))
pipeline=ref.HandLandmarker(None,None)
expected=[]
for d in dets:
    d=ref.project_detection(d,ref.letterbox_projection(640,480));rot=ref.compute_rotation(d['kp'][0][0]*640,d['kp'][0][1]*480,d['kp'][2][0]*640,d['kp'][2][1]*480)
    longest=max(d['w']*640,d['h']*480)*2.6
    expected.append([d['xmin']+d['w']/2+.5*480*d['h']*np.sin(rot)/640,d['ymin']+d['h']/2-.5*d['h']*np.cos(rot),longest/640,longest/480,rot])
out=np.empty((2016,5),np.float32);count=api.native_decode(boxes,scores,640,480,out)
assert count==len(expected);np.testing.assert_allclose(out[:count],expected,atol=2e-5)
image=rng.integers(0,256,(480,640,3),np.uint8);bgra=cv2.cvtColor(image,cv2.COLOR_RGB2BGRA)
errors=[]
for size in (192,224):
    for replicate in (False,True):
        for angle in (0,.4,-1.3,2.6):
            r=np.array([.45,.53,.7,.7*640/480,angle],np.float32);actual=np.empty((size,size,3),np.float32)
            api.native_crop(bgra,640,480,640*4,r,size,int(replicate),actual)
            expected=ref.crop_rotated_rect(image,r[0]*640,r[1]*480,r[2]*640,r[3]*480,r[4],size,cv2.BORDER_REPLICATE if replicate else cv2.BORDER_CONSTANT,affine=True)
            error=np.abs(actual-expected);errors.append([float(error.mean()),float(error.max())])
            assert error.mean()<.001 and error.max()<.04,errors[-1]
print(json.dumps({'native_parity':'PASS','random_roi_cases':100,'crop_cases':len(errors),'worst_crop_mean':max(e[0] for e in errors),'worst_crop_max':max(e[1] for e in errors)}))
