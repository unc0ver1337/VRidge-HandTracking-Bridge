#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p build/host
python3 ../scripts/convert_mobrecon.py
xcrun coremlcompiler compile assets/mobrecon.mlpackage build --platform ios --deployment-target 16.0
xcrun coremlcompiler compile assets/mobrecon.mlpackage build/host
cp assets/mobrecon-parity.json build/
SDK="$(xcrun --sdk iphoneos --show-sdk-path)"
xcrun --sdk iphoneos clang++ -std=c++17 -dynamiclib -arch arm64 -isysroot "$SDK" \
 -miphoneos-version-min=16.0 -fobjc-arc -fblocks -O2 -ffp-contract=off -Wall -Wextra \
 Sources/Bootstrap.mm Network/Network.mm Tracking/Tracker.mm Tracking/CoreMLTracker.mm \
 -framework Foundation -framework UIKit -framework AVFoundation -framework CoreML -framework Vision \
 -framework CoreMedia -framework CoreVideo -framework CoreImage -framework ImageIO -framework UserNotifications \
 -install_name @executable_path/Frameworks/VRidgeHandTracking.dylib -o build/VRidgeHandTracking.dylib
codesign --force --sign - build/VRidgeHandTracking.dylib
codesign --verify --strict build/VRidgeHandTracking.dylib
otool -L build/VRidgeHandTracking.dylib > build/load-commands.txt
