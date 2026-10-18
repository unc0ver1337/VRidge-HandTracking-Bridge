# Experimental validation

65 Python tests cover the existing MPBR protocol/PC decoder/input and IPA packaging, upstream source hashes, mesh topology and joint ordering. Native C++ tests check MobRecon ROI/crop/mirroring and 980 synthetic camera translations. Core ML export checks actual checkpoint outputs against PyTorch on real official demo images and mirrors. Native Vision+MobRecon smoke runs on macOS CPU_ONLY.

No hardware accuracy/FPS/heat or app install result is inferred from CI. On iPhone 16 / iOS18.5 verify installation, existing VRidge streaming, both hand roles, back-of-hand and edge rotations, occlusion with Joy-Con, packet loss/recovery and sustained heat. Capture is 640x480/30 FPS; inference may be slower. This private experimental IPA does not replace the main release.
