# Android Firmware QEMU Bench

[中文](README.md) · [Boundaries](docs/BOUNDARIES.md) · [Private inputs](docs/INPUTS.md)

**Source-only compatibility tooling for running a user's separately supplied automotive Android userspace on Windows x64/QEMU ARM64.** This is not a firmware distribution, an Android OS distribution, an Amap redistribution, or a full head-unit emulator.

No vehicle firmware, extracted vendor files, APKs, map data, proprietary UI assets, user disks, screenshots, or raw runtime logs are included.

## Ownership boundary

- **This project's original code:** launch orchestration, read-only sparse/NBD transport, RAM overlays, diagnostics, a minimal gralloc0/framebuffer adapter, and a live pixel viewer/input bridge.
- **Original firmware, supplied privately:** init, Bionic, ART/zygote, system_server, framework, SurfaceFlinger, HIDL/HWC adapter, system applications, vendor policy and libraries. These real programs execute; this project did not create or reimplement them.
- **External open-source dependencies:** QEMU, a generic Android-capable kernel, BusyBox/musl, SwiftShader, LLVM, Node.js, Python and Pillow. Download helpers retain their separate upstream provenance and licenses. Public AOSP HAL headers are identified and retain Apache-2.0 notices.
- **Optional private application:** Amap's APK, UI, trademarks, terms, maps and navigation engine belong to their respective rights holders, not this project. Users supply their own APK. No agreement acceptance is automated.

The repository MIT license applies only to its original adaptation code. It grants no rights to redistribute firmware, Amap, artwork or maps. See [BOUNDARIES.md](docs/BOUNDARIES.md) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Setup

1. Use Windows x64 and provide the matching [private inputs](docs/INPUTS.md). Configure `config.local.json`, or place `system.img`, `vendor.img`, `userdata.img` under ignored `local/firmware/`.
2. Run **Setup-Dependencies.cmd**. Existing tools/configured paths are reused first. Missing public dependencies are downloaded into `runtime/` with pinned digest checks; no firmware or APK is downloaded. Missing Python is bootstrapped from a pinned official embeddable archive.
3. Run **Run-Amap.cmd**, initially with `--apk "C:\Inputs\amap.apk"` if needed. The tested example is Amap Auto 9.5 ARM64. Once installed, the APK/data persist in a separate writable disk.

`python scripts/setup_dependencies.py --plan` shows the dependency plan. `--offline` reuses verified caches. Existing local configuration fields are preserved; no system package installation or PATH changes are performed.

The console prints `LIVE_VIEWER_URL`. The viewer displays actual SurfaceFlinger output and sends input to Android; it does not recreate the app UI. Default sessions end after 30 minutes.

## What is and is not emulated

A generic Android-capable kernel replaces the original hardware kernel. The original firmware userspace runs with local-only boot/HAL/mount adaptations. Exynos hardware, the original boot.img/DTB, VLM/QNX, vehicle services, GPS and the complete factory display stack are not emulated.

An Android 9/ARM64 firmware instance was observed booting and displaying Amap's real main screen. This is a version-specific observation, not a guarantee for other firmware. Default networking is disabled. Online map tiles, search, routing and positioning were not validated. Amap can show “no map data available.” A nominal 30 Hz display mode is not measured 30 FPS.

The experimental guest uses permissive SELinux, root diagnostics bound to loopback and selected RAM-mounted system app subsets. Do not expose the viewer/control ports to a network. See [SECURITY.md](SECURITY.md).

## Stop, test, publish

```powershell
python control.py 'sync'
python rollback.py
python -m unittest discover -s tests -v
python scripts/audit_public.py
python scripts/package_source.py --output reports/source-release.zip
```

Stopping discards RAM overlays, verifies source-image hashes, and preserves the private writable data disk. A source release is built from an audited allowlist, never by zipping the working folder. CI uses synthetic fixtures only and never requires or uploads firmware.

Independent research tooling; no affiliation or endorsement by the vehicle, firmware, application or upstream component vendors.
