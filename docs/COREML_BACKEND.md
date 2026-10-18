# MobRecon backend

See README for the active experimental backend. Previous MediaPipe/fasthands conversion and models are removed from this branch. Vision supplies only 2D ROI/chirality; the native MobRecon Core ML graph produces 21 wrist-relative joints in metres and 2D landmarks. Both projections are unmirrored/unrotated into the original camera frame before the existing translation/palm-pose packaging.

Public source/checkpoint hashes are in models/upstream.json. FP32 conversion parity and native smoke JSON are build artifacts, not iPhone accuracy or speed benchmarks.
