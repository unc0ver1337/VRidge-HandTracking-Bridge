# Yaw-only direction correction

The live user reported correct hand translation and up/down rotation, but reversed
left/right wrist rotation. All experimental grip rotations and GlassVR controller
offsets were reset. The active local configuration enables `space.invert_yaw`.

The correction is applied to the controller orientation expressed in the HMD
frame, before returning to raw tracking/world coordinates and pose filtering.
It negates the heading in a yaw/pitch/roll decomposition, preserving pitch and
roll. Positions are never reflected or changed. Heading is taken from the forward
axis directly, avoiding Euler conversion warnings; exactly vertical aim is left
unchanged because its horizontal heading is undefined.

`space.invert_yaw` defaults to false in the distributed configuration and is true
in this user's `hardware.local.yaml`. This is a user-selected yaw convention, not
a claim that the monocular estimator has become physically unambiguous.

44 automated tests passed, including sign reversal, pitch/roll preservation,
involution, arbitrary HMD heading, unchanged translations and vertical aim.
