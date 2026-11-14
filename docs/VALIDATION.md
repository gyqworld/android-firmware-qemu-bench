# Validation scope

## Source-release checks

The public test suite uses synthetic byte streams/filesystems and does not need
firmware, APKs, renderer binaries or sibling projects. It checks configuration,
newc archives, sparse-image reads, source-image read-only access, bounded archive
extraction, dependency cache integrity, the public manifest, the actual Git index,
and rejection of forced binary files or indexed secrets hidden by clean worktree
files.

The source ZIP was reopened member-by-member, then extracted into an isolated
temporary directory without adjacent firmware/tools. Unit tests, setup `--plan`,
launcher `--help` and public-source auditing passed there.

## Public dependency preparation

Observed on Windows x64: existing QEMU, LLVM, Node, Python, kernel and Alpine
bootstrap were reused; missing python-zstandard was downloaded and hash-checked.
A separate clean extraction with **no firmware present** downloaded the pinned
public renderer vendor member, extracted only its renderer files, and correctly
reported that private firmware link inputs were still required. Its offline
rerun performed no network download. No firmware or APK was fetched.

The portable Python/Node/LLVM/QEMU fallback code and pins are included, but every
all-missing-machine combination has not been runtime-tested. A digest change fails
closed rather than silently accepting a newer archive. Upstream signatures are
not claimed to be verified by these helpers.

## Local firmware runtime checks

After separating this release from the private experiment, a read-only ARM64
probe executed the supplied firmware's original Android shell and exited 0;
`rollback.py` verified the original system/vendor/userdata hashes. This verifies
the relocated launcher/transport, not a new cross-version GUI compatibility claim.

The earlier graphics experiment observed Android boot completion and Amap 9.5's
actual main screen using the same core adapter. That private observation does not
turn source-only CI into an Android boot test. Raw logs, screenshots, image hashes,
private host paths and user consent/data records are deliberately not published.

Online maps, routing and GPS were not validated. See the explicit origin and
runtime substitutions in [BOUNDARIES.md](BOUNDARIES.md).
