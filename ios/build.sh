#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
xcrun --sdk iphoneos clang++ -std=c++17 -dynamiclib -arch arm64 -isysroot "$SDK" \
  -miphoneos-version-min=15.0 -fobjc-arc -fblocks -O2 -Wall -Wextra \
  Sources/Bootstrap.mm Network/Network.mm Tracking/Tracker.mm \
  -framework Foundation -framework UIKit -framework Vision -framework AVFoundation \
  -framework CoreMedia -framework CoreVideo -framework CoreImage -framework ImageIO \
  -framework UserNotifications -install_name @executable_path/Frameworks/VRidgeHandTracking.dylib \
  -o build/VRidgeHandTracking.dylib
codesign --force --sign - build/VRidgeHandTracking.dylib
codesign --verify --strict build/VRidgeHandTracking.dylib
otool -L build/VRidgeHandTracking.dylib
