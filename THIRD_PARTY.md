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
release. The experimental client was tested by the owner before promotion to the main release. The original app is not authored or relicensed by
this project. Its executable is preserved by the update process.

**Google MediaPipe models**: stock fp16 palm/landmark weights, Apache-2.0; license in third_party/MediaPipe-LICENSE.txt. Two compiled Core ML models are bundled. MediaPipe Tasks SDK is not linked in 2.5. WHIM fine-tuned weights are not used. Assets and reference hashes are pinned in ios/fetch_dependencies.py.

Windows bundles Python, NumPy, SciPy, PyYAML, zeroconf, OpenVR Python bindings and PyInstaller runtime components. Collected notices remain in _internal. Apple frameworks are system components, not redistributed binaries.

No affiliation with Valve, Apple, RiftCat, or DaniXmir is claimed.


**Vimal Mollyn — fasthands / Core ML port.** The native pipeline is adapted from Vimal Mollyn's
Mediapipe-Hands-PyTorch-CoreML / fasthands (MIT), pinned revision
565d188 (full hash in ios/fetch_dependencies.py). License is preserved in
third_party/FastHands-LICENSE.txt. The bundled stock fp16 model weights are
Google MediaPipe weights (Apache-2.0); WHIM fine-tuned weights are not used.
The author reports performance on M4; this project does not claim those
measurements apply to iPhone 16 or two-hand tracking beside VRidge.
