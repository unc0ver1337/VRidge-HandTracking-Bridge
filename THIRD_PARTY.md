# Third-party attribution

This project is based on **[GlassVR by DaniXmir](https://github.com/DaniXmir/GlassVr)**
for SteamVR/OpenVR controller emulation. It does not introduce an independent
SteamVR driver. GlassVR implements the Index controller profile, device roles,
UDP packets and skeletal simulation used here.

Reviewed upstream revision: `4d530752a52febb39a3cb9ade3632e4c2ce77425`.
The release contains a locally rebuilt GlassVR DLL with the small
`patches/glassvr-stable-controller-connection.patch` change. Its original Viture object
and import libraries were reused because the upstream SDK headers are absent.
The build and this dependency limitation are recorded in
`docs/DRIVER_VISIBILITY_FIX.md`. GlassVR and its bundled dependencies remain
their authors' software; our MIT license does not relicense them. No upstream
license file was found in the inspected checkout; see the upstream project for
its distribution terms and contact its author for reuse permissions.

**VRidge 2 / RiftCat** is proprietary third-party software. The unsigned modified
IPA supplied in the release is based on the decrypted VRidge 2.7.8 IPA provided
by the project owner. The owner explicitly requested distribution of the IPA in the main project
release. The experimental client was tested by the owner before promotion to 2.0. The original app is not authored or relicensed by
this project. Its executable is preserved by the update process.

**MediaPipe by Google / Google AI Edge** supplies the on-device Hand Landmarker,
SDK 1.1.1 and hand_landmarker float16/v1 model. Source:
https://github.com/google-ai-edge/mediapipe . SDK source is Apache License 2.0;
the full license is in third_party/MediaPipe-LICENSE.txt. Model download/source:
https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker#models .
SDK and model hashes are pinned in ios/fetch_dependencies.py. Third-party code
and model assets retain their own distribution terms; our MIT license covers
our added code, not the model or proprietary VRidge.

Windows EXE bundles Python, NumPy, SciPy, PyYAML, zeroconf, OpenVR Python bindings
and PyInstaller runtime components. Collected dependency notices are preserved
in _internal. AVFoundation/OpenGLES and other Apple frameworks are system
frameworks, not redistributed binaries. MediaPipe SDK is statically linked in
the injected library; the .task model is included in the IPA.

No affiliation with Valve, Apple, RiftCat, or DaniXmir is claimed.
