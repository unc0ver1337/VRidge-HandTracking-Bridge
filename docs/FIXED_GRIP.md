# Fixed grip preset — 2.5.1

The owner centered both hands in the running 2.5 bridge and requested that exact
result as the default. The two `Space.session_grip` rotations were read from that
process without modifying its state or restarting it. Repeated reads matched.
Only the two xyzw quaternions are included in `pc/glassvr/grip.py`; process memory,
addresses, stack dumps and unrelated runtime data are not release content.

Each controller uses the same composition as the captured 2.5 session:

```text
R_controller = R_head_at_capture * R_camera_mount * R_phone_palm * Rx(90deg) * R_fixed_grip[side]
```

Position and the RawAndUncalibrated HMD coordinate path are unchanged. The grip
correction is applied on the right, in the controller's local frame. It must not
be moved to world/head space or applied again on the phone. Separate left/right
offsets are intentional: they reproduce the two separately centered hands.

The centering method, render-model tip lookup, held centering state and Xbox
chord interception are removed. Back and Start are ordinary left/right System
buttons, including simultaneous presses. No automatic centering, gesture input
or saved local orientation profile is loaded. Obsolete `grip_rotation_deg` in an
older YAML is ignored. Download and use the new Windows build to get this preset;
the old running EXE keeps its own session state until the owner closes it.

This is the owner's preferred grip convention, not universal extrinsic camera
calibration or a solution to monocular ambiguity. A different physical phone
mount or pose convention can require a different preset. Model failures,
occlusion or handedness errors can still produce wrong orientations. The final
2.5.1 package requires a real-device check after installation; synthetic tests
verify the exact composition, restart persistence and button behavior.
