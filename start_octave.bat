@echo off
echo ===================================================
echo   Starting Octave Context-Aware Spatial OS...
echo ===================================================

:: Start the C++ Engine in a separate window
echo Launching C++ Motor Engine...
cd build
start spider_slice1.exe
cd ..

:: Start the Electron UI
echo Launching Electron Dashboard...
cd ui
call npm install
npm run dev
