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

Controller forward -Z maps to the MediaPipe palm basis wrist-to-fingers +Y.
Hold Back+Start to center the controller rays toward HMD forward; the correction
lasts for this session only. See README for the current 2.0 installation steps.
