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

Version 2.5.1 applies fixed per-hand grip quaternions from the owner-approved
2.5 session. The Back+Start centering function and chord interception are removed;
both buttons remain ordinary per-hand System inputs, even when pressed together.
See FIXED_GRIP.md and README for installation and limitations.
