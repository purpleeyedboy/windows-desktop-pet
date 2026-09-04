---
name: desktop-pet-windows-release
description: Build and verify PyInstaller Windows artifacts, PowerShell gates, Actions workflows, hashes, and delivery state.
---

# Desktop Pet Windows Release

1. Declare reproducible build/test dependencies and keep runtime-only exclusions intact.
2. Build only on Windows for Windows acceptance; Linux compilation is not EXE proof.
3. Require one expected EXE, archive validation, a SHA-256 digest, and an uploaded artifact.
4. Preserve prior EXEs and use a new exact filename for each authorized candidate.
5. Report Actions build, download/hash verification, and real-desktop user acceptance as separate gates.
