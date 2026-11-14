# Native adapter provenance

The gralloc/framebuffer pixel transport and runtime probes are original bench
code. The Android HAL ABI declarations under include/hardware and include/cutils
are AOSP Android 9.0.0_r1, Apache-2.0, with upstream headers retained. See
../THIRD_PARTY_NOTICES.md and ../licenses/Apache-2.0.txt.

No firmware-derived headers or runtime binaries are included. The minimal
include/sys and include/system declarations are local compile scaffolding,
not a vendor SDK or complete NDK. Compiled libraries stay in ignored build/.
