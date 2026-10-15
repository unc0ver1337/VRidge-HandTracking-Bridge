"""Read real SteamVR skeletal actions, never inject synthetic motion."""
import pathlib,json,time,ctypes,openvr,numpy as np
root=pathlib.Path(__file__).resolve().parents[1]
folder=root/'artifacts/skeleton-probe';folder.mkdir(parents=True,exist_ok=True)
actions=[{'name':'/actions/probe/in/'+side,'type':'skeleton','skeleton':'/skeleton/hand/'+side,'requirement':'optional'} for side in ('left','right')]
manifest={'action_sets':[{'name':'/actions/probe','usage':'single'}],'actions':actions,'default_bindings':[{'controller_type':'knuckles','binding_url':'knuckles.json'}]}
binding={'controller_type':'knuckles','name':'Read-only skeletal probe','description':'Diagnostic read of real driver bones','bindings':{'/actions/probe':{'skeleton':[{'output':'/actions/probe/in/'+side,'path':'/user/hand/'+side+'/input/skeleton/'+side} for side in ('left','right')]}}}
(folder/'actions.json').write_text(json.dumps(manifest));(folder/'knuckles.json').write_text(json.dumps(binding))
openvr.init(openvr.VRApplication_Background)
try:
 vi=openvr.VRInput();vi.setActionManifestPath(str(folder/'actions.json'))
 actionset=vi.getActionSetHandle('/actions/probe');handles={s:vi.getActionHandle('/actions/probe/in/'+s) for s in ('left','right')}
 sets=(openvr.VRActiveActionSet_t*1)();sets[0].ulActionSet=actionset
 result={s:{'active_samples':0,'bone_count':None,'samples':[],'invalid_bone_samples':0,'max_aux_tip_error_m':0.,'errors':set()} for s in handles}
 deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  try:vi.updateActionState(sets)
  except Exception as e:
   for entry in result.values():entry['errors'].add(type(e).__name__+': '+str(e))
   time.sleep(.1);continue
  for side,handle in handles.items():
   entry=result[side]
   try:
    data=vi.getSkeletalActionData(handle)
    count=vi.getBoneCount(handle);entry['bone_count']=count
    if data.bActive:
     entry['active_samples']+=1
     bones=(openvr.VRBoneTransform_t*count)()
     vi.getSkeletalBoneData(handle,openvr.VRSkeletalTransformSpace_Parent,openvr.VRSkeletalMotionRange_WithoutController,bones)
     from scipy.spatial.transform import Rotation
     pos=np.array([list(b.position.v)[:3] for b in bones])
     quat=np.array([[b.orientation.x,b.orientation.y,b.orientation.z,b.orientation.w] for b in bones])
     valid=np.isfinite(pos).all() and np.isfinite(quat).all() and np.all(np.abs(np.linalg.norm(quat,axis=1)-1)<.002)
     if not valid:entry['invalid_bone_samples']+=1
     else:
      parents=[-1,0,1,2,3,4,1,6,7,8,9,1,11,12,13,14,1,16,17,18,19,1,21,22,23,24]
      wp=pos.copy();wr=Rotation.from_quat(quat)
      for i in range(1,26):
       parent=parents[i];wp[i]=wp[parent]+wr[parent].apply(pos[i]);wr[i]=wr[parent]*wr[i]
      error=float(np.max(np.linalg.norm(wp[[5,10,15,20,25]]-pos[26:31],axis=1)))
      entry['max_aux_tip_error_m']=max(entry['max_aux_tip_error_m'],error)
     entry['samples'].append([[b.orientation.w,b.orientation.x,b.orientation.y,b.orientation.z] for b in bones])
   except Exception as e:entry['errors'].add(type(e).__name__+': '+str(e))
  time.sleep(.03)
 output={'source':'real OpenVR Skeletal Input; no synthetic packets','hands':{}}
 for side,entry in result.items():
  samples=np.array(entry.pop('samples'));entry['errors']=sorted(entry['errors'])
  entry['max_bone_quaternion_component_range']=float(np.max(np.ptp(samples,axis=0))) if len(samples)>1 else 0
  output['hands'][side]=entry
 p=(root/'artifacts/skeleton-live.json');p.write_text(json.dumps(output,indent=2));print(json.dumps(output,indent=2))
finally:openvr.shutdown()
