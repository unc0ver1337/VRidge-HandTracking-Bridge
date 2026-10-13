# Head-relative positioning correction

Live testing on 2026-10-13 exposed a room-origin error: the bridge sampled HMD
poses in `Standing` and sent them to GlassVR as raw driver poses. SteamVR then
applied its raw-to-standing room transform a second time. In the live setup that
transform contained about [2.012, 1.131, 0.392] metres of translation and a yaw
rotation, moving controller models away from the headset.

The HMD history now samples `TrackingUniverseRawAndUncalibrated`, matching
GlassVR's identity `qWorldFromDriverRotation`. A measured camera-space point is
transformed by:

```
controller_raw = hmd_position_raw + hmd_rotation_raw *
                 (camera_mount_offset + camera_to_hmd_rotation * hand_camera)
```

With the phone display facing the eyes and rear camera looking forward, camera
positive depth maps to HMD local -Z, the direction of the headset's view. Camera
right/down map to headset right/down, subject to the actual landscape mounting
rotation. Room calibration/recentering is applied subsequently by SteamVR.

A regression test verifies the head-relative displacement under HMD yaw and an
independent translated/rotated room transform. All 41 automated tests passed.
The phone reconnected after the corrected bridge restart and real right-hand
reconstruction resumed. Correct visual grip orientation and both-hand motion
still require live observation and mount calibration.
