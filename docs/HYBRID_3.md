# Hybrid 3.0: geometry and validation

The runtime uses Vision's wrist + index/middle/ring/little MCP observations.
The palm template is an approximate planar anatomical prior, not population-fit
anthropometry. It is scaled to configured MCP breadth; shape mismatch produces
systematic depth/rotation error. Finger tips never enter the pose solver.
OpenCV IPPE supplies two planar solutions. Positive depth and <=12 px reprojection
are required; comparable solutions favour temporal SO(3) continuity. The 2 px/rad
continuity cost resolves near ties without making neural articulation a pose input.
Angular changes above 600 deg/s plus 8 deg per observation are rejected as branch
jumps. At near edge-on projected palm area (<0.08 normalized) recent orientation
is held; without a recent sample it remains explicitly ambiguous. After a >350 ms
gap the prior is discarded, since an occluded hand may genuinely have turned.
These are tunable engineering rejection thresholds, not calibrated covariances.

The palm is not rigid and is not exactly planar. Confidence below .35 at any of
the five anchors rejects the observation. The conservative depth uncertainty
floor is 15% of estimated range, increased by normalized reprojection error.
This floor is a quality indicator, not a statistically validated standard deviation.
Camera intrinsics come from the source sample attachment; center crop applies the
same affine change to K and image. Geometric distortion correction is enabled
where supported; fallback FOV uses its corrected value. Apple documents GDC's
field-of-view tradeoff at https://developer.apple.com/documentation/avfoundation/avcapturedevice/isgeometricdistortioncorrectionsupported?language=objc .
Residual distortion and any FOV-derived intrinsics remain accuracy limitations.

Capture stays in unmirrored native landscape sensor orientation. Vision uses
orientation Up and its lower-left UV coordinates are converted to top-left y-down
once. Core ML receives rotated crops from the same source frame; its world basis
is reconstructed independently when estimating articulation. Side comes from the
Vision ROI, not a second classifier. The PC uses temporal identity association.
Fully occluded crossings cannot be solved unambiguously by these observations.

Pose is targeted at 30 FPS; the dedicated finger worker has no backlog and accepts
at most 15 source frames/s. Cached fingers expire after 250 ms and a large wrist
displacement; each packet carries their actual source timestamp. Inference overlap
can still compete for CPU/ANE: 30 FPS is not established until device measurements.
Core ML is configured CPUAndNeuralEngine, which does not prove actual ANE placement.

The HMD is sampled in RawAndUncalibrated coordinates at capture time; SteamVR
applies its room transform once. One Euro position/rotation filtering and bounded
prediction remain independent of finger smoothing. Centering changes the grip
quaternion only and saves to a backend-specific atomic JSON on release.

Automated checks include synthetic known-pose recovery for both hands, noisy
continuous turns, missing palm anchors, neural articulation changes that must not
affect controller pose, stale finger TTL, protocol version/timestamp/packet loss,
both-hand centering/reload, XInput disconnect, driver bootstrap/uninstall with mocked
system actions, real local UDP packet compatibility, native Core ML parity and
production Vision extraction → finger-only Core ML inference on original/mirrored
photographs. macOS CPU image tests do not establish iPhone camera/ANE/VRidge FPS.

Device acceptance: use matched 3.0 IPA+EXE, decline once to check VRidge remains
usable; relaunch and accept; show each hand and both hands; center with Back+Start;
turn palms slowly, curl fingers with a stationary wrist, briefly occlude a hand,
then compare console FPS/loss/latency and SteamVR pose/skeleton for 5–10 minutes.
Record actual FPS and frame latency before describing this version as faster.
