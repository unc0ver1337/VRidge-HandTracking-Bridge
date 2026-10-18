$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
& .venv\Scripts\python.exe -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller install failed' }
& .venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onedir --name VRidgeHandBridge --paths . --collect-all openvr --collect-all zeroconf --exclude-module pytest --distpath artifacts/windows --workpath build/windows scripts/windows_entry.py
if ($LASTEXITCODE -ne 0) { throw 'Windows build failed' }
Copy-Item pc/config.yaml artifacts/windows/VRidgeHandBridge/config.yaml -Force
Set-Content -Encoding ascii artifacts/windows/VRidgeHandBridge/Start-Bridge.cmd '@echo off', 'cd /d "%~dp0"', 'VRidgeHandBridge.exe --config config.yaml', 'pause'

& .venv/Scripts/python.exe scripts/fetch_glassvr.py artifacts/windows/VRidgeHandBridge/GlassVR/glassvrdriver
if ($LASTEXITCODE -ne 0) { throw "Driver assembly failed" }
Copy-Item Uninstall-GlassVR.cmd artifacts/windows/VRidgeHandBridge/Uninstall-GlassVR.cmd -Force
