# Current Xbox layout (supersedes the original README mapping)

Both hands receive input independently with `mapping.layout: dual`.

| Xbox | Index input |
|---|---|
| X / Y | Left / right B (game menu binding) |
| Back / Start | Left / right System |
| LT / RT | Left / right analog trigger |
| LB / RB | Left / right grip |
| Left / right stick | Left / right thumbstick |
| LS / RS click | Left / right thumbstick click |

A/B Xbox remain unassigned. Start/Back no longer calibrate/reset. Game menu
behavior depends on the game's SteamVR binding for Index B. Trackpads are unused.
Disconnect releases both hands. InputManager still suppresses input for a hand
without a recent tracked pose.

Controller forward -Z now maps to the kinematic hand's wrist-to-fingers +Y axis
through a fixed Rx(90 degrees) basis conversion, rather than the palm normal.
Position and HMD attachment remain unchanged. No yaw inversion or experimental
calibration is enabled. Monocular ambiguity remains; real hardware verification
of orientation and buttons is pending. All 43 automated tests passed locally.
