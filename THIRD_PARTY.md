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
by the project owner, who explicitly requested its public distribution. The
original app is not authored or relicensed by this project. The added dynamic
library is our code; original executable code and resources remain VRidge's.

Windows EXE bundles Python, NumPy, SciPy, PyYAML, zeroconf, OpenVR Python bindings
and PyInstaller runtime components. Dependency license/notices collected by
PyInstaller are preserved in the `_internal` distribution directory. Apple
Vision/AVFoundation are system frameworks on iOS, not redistributed frameworks.

No affiliation with Valve, Apple, RiftCat, or DaniXmir is claimed.
