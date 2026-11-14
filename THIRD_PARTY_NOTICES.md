# Third-party components and private inputs

The repository MIT license covers original bench orchestration, transport,
display adaptation and tests. It does not relicense firmware, applications,
maps, UI resources or third-party components.

## Included source

| Files | Provenance / license |
|---|---|
| `native/include/hardware/*.h`, `native/include/cutils/native_handle.h` | Android Open Source Project, Android 9.0.0_r1; Apache-2.0, original headers retained; full text in `licenses/Apache-2.0.txt` |
| `native/include/sys/*`, `native/include/system/graphics.h` | Minimal local compile declarations, not vendor SDKs or extracted firmware headers |
| `sparse_nbd.py`, dependency helpers | Reused/adapted source from the related MIT bench `mib3-hmi-bench`; license retained in `licenses/mib3-hmi-bench-MIT.txt` |
| `tools/extract_ext4_sparse.js` | Source-only local ext4/Android sparse reader authored for the bench; no filesystem contents embedded |

AOSP source links:
- https://android.googlesource.com/platform/hardware/libhardware/+/refs/tags/android-9.0.0_r1/include/hardware/
- https://android.googlesource.com/platform/system/core/+/refs/tags/android-9.0.0_r1/libcutils/include/cutils/native_handle.h

Related source reuse: Copyright (c) 2026 mib3-hmi-bench contributors, MIT.
The original permission notice and disclaimer are retained verbatim in
`licenses/mib3-hmi-bench-MIT.txt`.

## Downloaded separately; no runtime binaries shipped in this repository

- **QEMU / MSYS2:** GPL and component-specific licenses. Portable extraction
  keeps upstream license directories. https://www.qemu.org/ / https://www.msys2.org/
- **AOSP Android-capable kernel:** GPL-2.0 and kernel component notices;
  fixed prebuilt blob/image hashes, source reference in `prepare.py`.
  https://android.googlesource.com/kernel/goldfish/
- **Alpine initramfs:** BusyBox GPL-2.0 and musl MIT, plus component licenses.
  Only BusyBox/musl enter generated private initramfs archives. Separate binary
  redistribution must satisfy upstream obligations. https://alpinelinux.org/
- **SwiftShader:** Apache-2.0 and bundled notices. Only three pinned libraries
  are extracted from the official Google ARM64 vendor archive for local use.
  This does not make the entire SDK or its download terms MIT; review applicable
  SDK terms. https://swiftshader.googlesource.com/SwiftShader/ /
  https://android.googlesource.com/platform/external/swiftshader/
- **LLVM:** Apache-2.0 WITH LLVM-exception and component licenses. https://llvm.org/
- **Python:** PSF and included licenses. https://www.python.org/
- **Node.js:** MIT and included third-party notices. https://nodejs.org/
- **Pillow:** HPND and bundled third-party licenses. https://python-pillow.org/
- **python-zstandard:** BSD-3-Clause/component notices. https://github.com/indygreg/python-zstandard

Dependency locks contain metadata/URLs/hashes only. Download availability and
integrity checks grant no new redistribution rights. The source packager excludes
all downloads. Retain upstream notices and source obligations for any separate
binary distribution.

## Not supplied or downloaded

Vehicle firmware, derived libraries/RC/policy/classes/resources, APKs, maps and
account/user data remain private inputs. Some Android components originate in
AOSP, but this repository does not bundle extracted firmware binaries or assert
one license for an entire vendor image. Amap's UI, trademarks, engine and maps
are not original project code.
