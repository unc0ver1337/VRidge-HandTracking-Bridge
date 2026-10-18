# MobRecon Core ML backend — 2.6

The user-tested MobRecon preview is promoted without changing its weights, FP32 precision, crop/projection math or runtime settings. Vision supplies only 2D ROI and chirality. Core ML produces 21 wrist-relative joints in metres and 2D landmarks through the trained MobRecon mesh decoder. Both outputs are unmirrored/unrotated into the original camera frame before existing camera-translation fitting and palm-pose packaging.

Source/checkpoint/topology hashes: models/upstream.json. Conversion parity and native smoke JSON: iOS/library in the release. These are macOS CPU_ONLY checks, not an iPhone FPS/ANE/accuracy benchmark. Capture stays640x480/30 FPS; actual throughput and heat need measurement. No dependency on the temporary private repo remains.
