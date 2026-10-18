# Third-party attribution — 2.6

## MobRecon / HandMesh — Xingyu Chen and coauthors

Official revision 3c87e958d4855f890e3884ec94bcfc0f99422c3d of https://github.com/SeanChenxy/HandMesh . Source MIT notice is retained in third_party/MobRecon-LICENSE.txt. The official 2023 DenseStack + SpiralConv demo checkpoint is SHA256-pinned in models/upstream.json. The Core ML graph retains the learned backbone, mesh decoder and joint regression. Integer-to-float clip casts and equivalent dense pooling are validated numerically; trained parameters are unchanged. FP32 export is used because FP16 failed the chosen parity tolerance.

Topology/regressor derive from upstream template/transform.pkl, j_reg.npy and OpenMesh1.2.1 spiral extraction, length9/dilation1. MANO_RIGHT.pkl was not downloaded and no license agreement was accepted by automation. MIT integration/source does not replace any applicable model/weight or MANO asset terms; see https://mano.is.tue.mpg.de/ and upstream before further redistribution. Test photographs come from upstream cmr/images.

## GlassVR — DaniXmir

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

## Earlier Core ML backend — Vimal Mollyn / Google MediaPipe

Vimal Mollyn's fasthands / Mediapipe-Hands-PyTorch-CoreML was the basis of the 2.5 backend. Its MIT notice remains in third_party/FastHands-LICENSE.txt. The Google MediaPipe Apache-2.0 notice remains in third_party/MediaPipe-LICENSE.txt for history. MediaPipe inference models and that pipeline are not included in the 2.6 IPA. Vision supplies only ROI and chirality; MobRecon supplies 3D.

## VRidge — RiftCat

VRidge2.7.8 is proprietary and supplied by the owner as a decrypted IPA. The owner requested release distribution; our MIT license does not relicense the app or assert third-party rights. The original executable is preserved. App content, profiles and certificates are excluded from git/CI; unsigned IPA packaging occurs locally.

## Dependencies

Windows bundles Python, NumPy, SciPy, PyYAML, zeroconf, OpenVR bindings and PyInstaller components; collected notices remain in _internal. Apple Vision/Core ML/AVFoundation are system frameworks, not redistributed framework binaries. No affiliation with Apple, Valve, RiftCat or the upstream authors is claimed.
