# Experimental security model

- Local compatibility research tooling, not a production Android VM.
- Supplied firmware/apps execute real code in QEMU. Run only intended inputs.
- Source images are read-only NBD and `ro,noload` mounts; the separate data disk
  holds private application state.
- SELinux is permissive inside the experimental guest; original secure boot is
  not reproduced. No Windows security settings are changed.
- Viewer/NBD/root diagnostics bind `127.0.0.1`. The root diagnostic channel has
  no authentication; local processes can access it. Never forward these ports.
- Guest networking is disabled by default. No real account, GPS or vehicle feed
  is required for the demonstrated screen.
- `rollback.py` verifies process identity; it preserves app data and does not
  reset an app, revoke permissions or delete accounts.
- Run the public audit and use only the allowlist source packager. Do not upload
  private reports, frames, data disks, APKs or firmware to Issues/Actions.

Report source issues without attaching private inputs or logs. No host isolation
certification is claimed.
