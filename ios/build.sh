#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
python3 fetch_dependencies.py
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
FRAMEWORK_ARGS=()
for NAME in MediaPipeTasksCommon MediaPipeTasksVision; do
  FOUND=$(find deps -type d -name "$NAME.framework" -path '*/ios-arm64/*' | head -1)
  test -n "$FOUND" || { find deps -maxdepth 4 -type d; exit 1; }
  FRAMEWORK_ARGS+=(-F "$(dirname "$FOUND")" -framework "$NAME")
done
GRAPH=$(find deps -type f -name '*.a' -path '*MediaPipeTaskGraphs*ios-arm64/*' | head -1)
test -n "$GRAPH" || { find deps -type f | head -60; exit 1; }
FRAMEWORK_ARGS+=("$GRAPH")
xcrun --sdk iphoneos clang++ -std=c++17 -dynamiclib -arch arm64 -isysroot "$SDK" \
  -miphoneos-version-min=15.0 -fobjc-arc -fblocks -O2 -Wall -Wextra \
  Sources/Bootstrap.mm Network/Network.mm Tracking/Tracker.mm \
  "${FRAMEWORK_ARGS[@]}" -Wl,-all_load -Wl,-ObjC -lz -lsqlite3 \
  -framework Foundation -framework UIKit -framework AVFoundation -framework Accelerate \
  -framework CoreMedia -framework CoreVideo -framework CoreImage -framework ImageIO \
  -framework AudioToolbox -framework CoreGraphics -framework QuartzCore -framework Metal -framework MetalKit -framework OpenGLES \
  -framework UserNotifications -install_name @executable_path/Frameworks/VRidgeHandTracking.dylib \
  -o build/VRidgeHandTracking.dylib
cp assets/hand_landmarker.task build/hand_landmarker.task
codesign --force --sign - build/VRidgeHandTracking.dylib
codesign --verify --strict build/VRidgeHandTracking.dylib
otool -L build/VRidgeHandTracking.dylib
