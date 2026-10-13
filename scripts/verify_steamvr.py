"""Read real OpenVR controller state without inventing success. Exit 2 if absent."""
import json,time,sys
import openvr

def main():
    initialized=False
    try:
        openvr.init(openvr.VRApplication_Background);initialized=True;vr=openvr.VRSystem();result={}
        for role,name in ((openvr.TrackedControllerRole_LeftHand,'left'),(openvr.TrackedControllerRole_RightHand,'right')):
            i=vr.getTrackedDeviceIndexForControllerRole(role)
            if i==openvr.k_unTrackedDeviceIndexInvalid:result[name]={'present':False};continue
            poses=vr.getDeviceToAbsoluteTrackingPose(openvr.TrackingUniverseStanding,0,openvr.k_unMaxTrackedDeviceCount)
            p=poses[i];ok,state=vr.getControllerState(i)
            result[name]={'present':bool(p.bDeviceIsConnected),'valid_pose':bool(p.bPoseIsValid),'serial':vr.getStringTrackedDeviceProperty(i,openvr.Prop_SerialNumber_String),'input_readable':bool(ok),'packet_number':state.unPacketNum if ok else None}
        print(json.dumps(result,indent=2))
        return 0 if all(r.get('present') and r.get('valid_pose') and r.get('input_readable') for r in result.values()) else 2
    except Exception as e:print('SteamVR hardware verification unavailable:',type(e).__name__,repr(e));return 2
    finally:
        if initialized:openvr.shutdown()

if __name__=='__main__':sys.exit(main())
