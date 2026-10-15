# Continuous centering and hand visibility

Hold Back + Start to continuously align the controller tip ray with HMD forward.
The Index render model's actual `tip` component rotation is queried from OpenVR;
the controller body and tip do not have identical axes. Each fresh hand pose
updates the neutral correction while held. Releasing stops calibration and saves
the offsets in `pc/orientation.local.yaml`. Positions remain camera tracked.

Each hand independently expires 350ms after its last successfully emitted fresh
pose. The bridge releases input and switches `enable cl` / `enable cr` in the
existing GlassVR settings file to false. GlassVR's driver reports that device as
disconnected, rather than displaying a frozen controller. A fresh valid pose
reenables it. Loss of both hands or the phone disables both; bridge shutdown also
disables both. Settings writes are isolated in a worker and retry file contention.

This supersedes README's original frozen-controller limitation: the UDP format
still has no validity field, but device visibility now uses GlassVR's live config.
The bridge must own the enable flags while running; don't toggle them manually in
GlassVR simultaneously. A hard process kill cannot run shutdown cleanup.
