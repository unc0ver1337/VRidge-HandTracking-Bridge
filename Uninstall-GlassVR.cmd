@echo off
cd /d "%~dp0"
if exist "VRidgeHandBridge.exe" (
  VRidgeHandBridge.exe --uninstall-driver
) else (
  echo Run this file from the Windows release folder beside VRidgeHandBridge.exe.
)
pause
