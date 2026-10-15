# GlassVR disconnected pose fix — live validation 2026-10-15

The upstream driver always reported poseIsValid=true and Running_OK, including
when enable cl/cr was false. Live OpenVR inspection showed disconnected=true's
opposite (bDeviceIsConnected=false), but bPoseIsValid=true; rendered models could
remain frozen. The attached minimal patch sets poseIsValid=deviceIsConnected and
uses TrackingResult_Uninitialized while disabled.

Patched local GlassVR was built with MSVC v143 x64 Release. The source tree lacks
Viture SDK headers, so its original shipped viture.obj/glasses.lib/hidapi.lib were
reused, while the other translation units were rebuilt. This is a local build,
not a fully from-source rebuild of the proprietary Viture dependency. Compiler
conversion warnings and linker LNK4098 were present; no build errors remained.

The original installed DLL was backed up locally under artifacts/driver_glassvr-original.dll.
The patched DLL is artifacts/driver_glassvr-visibility-fix.dll, SHA256:
ee3be732e3022a6ce4bf62d4456ec5d2e1c74775b9d276372055f8ce179250bb

After installation and SteamVR restart, real OpenVR inspection returned:

```
left role: invalid; device 2: connected=false, poseValid=false
right role: invalid; device 3: connected=false, poseValid=false
```

Thus disabled controllers no longer retain valid poses. Game-specific rendering
and repeated loss/reacquisition still need observation. This patch requires a
driver rebuild and one SteamVR restart to load; restarting only Python is not
sufficient. Reinstalling the original GlassVR driver removes this fix.
