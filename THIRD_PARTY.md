# Experimental MobRecon attribution

MobRecon / HandMesh by Xingyu Chen et al., official revision 3c87e958d4855f890e3884ec94bcfc0f99422c3d. Source license: MIT, copied as third_party/MobRecon-LICENSE.txt. Selected source files are vendored unchanged except exact integer-to-float clip bounds for Core ML compatibility. Runtime pooling is replaced with equivalent dense matrix multiplication and checked numerically. The original model weights are SHA256 pinned in models/upstream.json.

Topology uses the upstream template/transform.pkl, j_reg.npy and OpenMesh 1.2.1 spiral extraction with length9/dilation1, matching the official 2023 SpConv demo. No MANO_RIGHT.pkl was downloaded or license agreement accepted by automation. Preprocessed topology/regressor are MANO-derived upstream assets; source MIT does not replace any applicable MANO asset terms. See https://mano.is.tue.mpg.de/ and upstream licensing before redistributing model assets beyond this private experiment.

The small test photographs are from HandMesh/cmr/images and retain upstream terms. Model conversion is float32; fp16 failed the chosen parity threshold. We do not claim phone FPS/ANE placement or improved real-world accuracy without hardware checks.

Vision, Core ML and AVFoundation are Apple system frameworks. No MediaPipe inference model is included in this IPA. Prior project history may contain MediaPipe code/attribution; it is not this backend.

GlassVR by DaniXmir supplies SteamVR emulation through the unchanged PC bridge. See main project's third-party documentation for driver build/dependency/distribution limitations. This repo does not relicense GlassVR.

VRidge/RiftCat is proprietary. The owner-provided decrypted app is packaged locally only; original executable preserved, signatures removed. IPA and signing material are excluded from git/CI. Our MIT license covers added integration code only.
