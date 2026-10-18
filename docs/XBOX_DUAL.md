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

A/B Xbox remain unassigned. Start/Back individually send System. Game menu
behavior depends on the game's SteamVR binding for Index B. Trackpads are unused.
Disconnect releases both hands. InputManager still suppresses input for a hand
without a recent tracked pose.

In 3.0 holding Back+Start continuously centers each visible hand toward the HMD
look direction. Release saves vision-hybrid-centering.json. Both System buttons
are suppressed during the chord until both are released. See README and HYBRID_3.md.
