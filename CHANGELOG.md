# Changelog

## 1.1.0

- Stabilized Electron startup and Python engine boot on Windows.
- Fixed duplicate IPC registration and safer single-instance behavior.
- Hardened packaged app startup with persistent main-process logging.
- Rebuilt the bundled backend during Windows packaging to avoid stale service binaries.
- Fixed packaged backend imports for Mediapipe and bundled the missing Matplotlib dependency.
- Improved camera ownership, gesture persistence, and custom static gesture management.
- Added a cleaner Windows installer flow for release packaging.
