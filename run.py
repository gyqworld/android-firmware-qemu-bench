"""Isolated read-only firmware Android boot experiments on the existing QEMU."""
from contextlib import ExitStack
from pathlib import Path
import argparse
import datetime
import gzip
import hashlib
import importlib.util
import json
import os
import re
import socket
import struct
import subprocess
import time

D = Path(__file__).resolve().parent
from config import load

CONFIG = None

def paths():
    return CONFIG if CONFIG is not None else load()


def digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def entry(name, content=b"", mode=0o100644, inode=1):
    n = name.encode()
    fields = [inode, mode, 0, 0, 1, 0, len(content), 0, 0, 0, 0, len(n) + 1, 0]
    b = b"070701" + b"".join(f"{x:08x}".encode() for x in fields) + n + b"\0"
    b += b"\0" * (-len(b) % 4)
    b += content
    return b + b"\0" * (-len(content) % 4)


def alpine_members():
    data = gzip.decompress(Path(paths()['initramfs']).read_bytes())
    o = 0
    wanted = {}
    while o + 110 <= len(data):
        if data[o:o + 6] not in (b"070701", b"070702"):
            o = data.find(b"070701", o + 1)
            if o < 0:
                break
        f = [int(data[o + 6 + i * 8:o + 14 + i * 8], 16) for i in range(13)]
        n = data[o + 110:o + 110 + f[11] - 1].decode()
        start = (o + 110 + f[11] + 3) & ~3
        if n in ("usr/bin/busybox", "usr/lib/ld-musl-aarch64.so.1"):
            wanted[n] = data[start:start + f[6]]
        o = (start + f[6] + 3) & ~3
    assert len(wanted) == 2
    return wanted


def build_initramfs(output, mode,apk=None):
    wanted = alpine_members()
    members = {}
    for n in ["bin", "sbin", "lib", "dev", "proc", "sys", "mnt", "bench"]:
        members[n] = (b"", 0o040755)
    members["bin/busybox"] = (wanted["usr/bin/busybox"], 0o100755)
    members["lib/ld-musl-aarch64.so.1"] = (wanted["usr/lib/ld-musl-aarch64.so.1"], 0o100755)
    members["bin/sh"] = (b"busybox", 0o120777)
    members["bench-init"] = ((D / "guest-init.sh").read_bytes(), 0o100755)
    # BusyBox switch_root checks that the old initramfs has a regular /init.
    members["init"] = ((D / "guest-init.sh").read_bytes(), 0o100755)
    members["bench/observer.sh"] = ((D / "observer.sh").read_bytes(), 0o100755)
    members["bench/control.sh"] = ((D / "control.sh").read_bytes(), 0o100755)
    members["bench/bench.rc"] = ((D / "bench.rc").read_bytes(), 0o100644)
    members["bench/mode"] = (mode.encode(), 0o100644)
    if mode=='graphics':
        members['bench/entropy']=(os.urandom(64),0o100600)
        for n in ['display.rc','display-port.sh','autostart-amap.sh']:
            members['bench/'+n]=((D/n).read_bytes(),0o100755 if n.endswith('.sh')else 0o100644)
        if apk:members['bench/apk-bytes']=(str(apk.stat().st_size).encode(),0o100644)
        for n in ['gralloc.bench.so','libEGL_swiftshader.so','libGLESv1_CM_swiftshader.so','libGLESv2_swiftshader.so','egl-probe','seed-rng']:
            members['bench/'+n]=((D/'build'/n).read_bytes(),0o100755)
    data = b"".join(entry(n, b, m, i + 1) for i, (n, (b, m)) in enumerate(members.items()))
    data += entry("TRAILER!!!", inode=999)
    output.write_bytes(gzip.compress(data, mtime=0))
    return [{"path": n, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
            for n, (b, _) in members.items()]


def source_manifest():
    result = {}
    for n in ['system.img', 'vendor.img', 'userdata.img']:
        p = Path(paths()['firmware_dir']) / n
        result[n] = {"bytes": p.stat().st_size, "sha256": digest(p)}
    return result


def main():
    global CONFIG
    ap = argparse.ArgumentParser(description='Run a local firmware Android userspace; no firmware is included.')
    ap.add_argument('--config',type=Path,default=D/'config.local.json')
    ap.add_argument("--mode", choices=["probe", "original", "headless", "graphics"], default="headless")
    ap.add_argument("--seconds", type=int, default=180)
    ap.add_argument('--apk',type=Path)
    args = ap.parse_args()
    CONFIG = load(args.config)
    from doctor import check
    check(CONFIG, args.mode)
    oldsession = D / 'output/session.json'
    if oldsession.exists():
        previous = json.loads(oldsession.read_text())
        if previous.get('state') == 'running':
            pid = int(previous['qemu_pid'])
            p = subprocess.run(['powershell', '-NoProfile', '-Command',
                f"Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' | Select-Object Name,CommandLine | ConvertTo-Json -Compress"], capture_output=True, text=True)
            if p.returncode != 0:
                raise RuntimeError('Could not check previous session identity')
            if p.stdout.strip():
                found = json.loads(p.stdout)
                if found.get('Name') == 'qemu-system-aarch64.exe' and str(D / 'output') in (found.get('CommandLine') or ''):
                    raise RuntimeError('This experiment already has a running VM; stop it with rollback.py first')
    if not 5 <= args.seconds <= 1800:
        ap.error("seconds must be 5..1800")
    output = D / "output" / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + args.mode)
    output.mkdir(parents=True)
    protected = D / "original-sources.local.json"
    if not protected.exists():
        protected.write_text(json.dumps({'firmware_dir':CONFIG['firmware_dir'],'files':source_manifest()}, indent=2) + "\n")
    record = {"mode": args.mode, "started_at": datetime.datetime.now().isoformat(),
              "original_images_readonly": True, "host_timeout": False}
    initrd = output / "initramfs.gz"
    record["initramfs_members"] = build_initramfs(initrd, args.mode,args.apk)
    import sparse_nbd as mod
    start = time.monotonic()
    with ExitStack() as stack:
        servers = []
        for name in ["system", "vendor", "userdata"]:
            s = mod.SparseNBDServer(Path(CONFIG['firmware_dir']) / f'{name}.img')
            stack.callback(s.close)
            servers.append(s)
        apkserver=None
        if args.apk:
            class RawImage:
                def __init__(self,path):
                    self.path=Path(path).resolve();self.file=self.path.open('rb');self.size=(self.path.stat().st_size+511)&~511
                def read(self,offset,length):
                    if offset<0 or length<0 or offset+length>self.size:raise ValueError('Range')
                    self.file.seek(offset);return self.file.read(length).ljust(length,b'\0')
                def close(self):self.file.close()
            original=mod.SparseImage;mod.SparseImage=RawImage
            try:apkserver=mod.SparseNBDServer(args.apk)
            finally:mod.SparseImage=original
            stack.callback(apkserver.close)
            record['apk']={'path':str(args.apk.resolve()),'bytes':args.apk.stat().st_size,'sha256':digest(args.apk)}
        qemu = Path(CONFIG['qemu'])
        cmdline = "console=ttyAMA0 earlycon=pl011,0x9000000 loglevel=8 rdinit=/bench-init panic=-1 androidboot.hardware=bench androidboot.selinux=permissive androidboot.console=ttyAMA0 androidboot.serialno=QEMU_BENCH androidboot.verifiedbootstate=orange androidboot.slot_suffix= androidboot.boot_devices=virtio"
        argv = [str(qemu), "-machine", "virt,gic-version=2", "-cpu", "cortex-a57",
                "-accel", "tcg,thread=multi", "-smp", "4", "-m", "4096" if args.mode=='graphics'else'2048',
                "-display", "none", "-serial", "stdio", "-monitor", "none", "-no-reboot",
                "-nic", "none", "-kernel", str(Path(CONFIG['kernel'])),
                "-initrd", str(initrd), "-append", cmdline]
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            control_port = sock.getsockname()[1]
        argv += ["-device", "virtio-serial-device", "-chardev",
                 f"socket,id=control,host=127.0.0.1,port={control_port},server=on,wait=off",
                 "-device", "virtserialport,chardev=control,name=bench.control"]
        viewer=None;viewer_url=None
        if args.mode=='graphics':
            with socket.socket()as sock:sock.bind(('127.0.0.1',0));frame_port=sock.getsockname()[1]
            argv += ['-chardev',f'socket,id=display,host=127.0.0.1,port={frame_port},server=on,wait=off','-device','virtserialport,chardev=display,name=bench.display']
        for i, s in enumerate(servers):
            argv += ["-drive", f"file=nbd://127.0.0.1:{s.port},format=raw,if=none,id=d{i},readonly=on",
                     "-device", f"virtio-blk-device,drive=d{i}"]
        if apkserver:
            argv += ['-drive',f'file=nbd://127.0.0.1:{apkserver.port},format=raw,if=none,id=apk,readonly=on','-device','virtio-blk-device,drive=apk,serial=bench-apk']
        if args.mode=='graphics':
            data=D/'data/userdata.ext4';data.parent.mkdir(exist_ok=True)
            if not data.exists():
                import ctypes,msvcrt
                with data.open('wb')as f:
                    returned=ctypes.c_ulong();ctypes.windll.kernel32.DeviceIoControl(ctypes.c_void_p(msvcrt.get_osfhandle(f.fileno())),0x900c4,None,0,None,0,ctypes.byref(returned),None)
                    f.truncate(4*1024**3)
            argv += ['-drive',f'file={data.as_posix()},format=raw,if=none,id=benchdata,discard=unmap,detect-zeroes=unmap','-device','virtio-blk-device,drive=benchdata,serial=bench-data']
        record.update(argv=argv, kernel_sha256=digest(Path(CONFIG['kernel'])), qemu_sha256=digest(qemu))
        print("OUTPUT=" + str(output), flush=True)
        with (output / "serial.log").open("wb") as stdout, (output / "qemu.stderr.log").open("wb") as stderr:
            process = subprocess.Popen(argv, stdout=stdout, stderr=stderr)
            if args.mode=='graphics':
                from display_viewer import FrameViewer
                viewer=FrameViewer(frame_port,output);stack.callback(viewer.close);viewer_url=viewer.url
                print('LIVE_VIEWER_URL='+viewer_url,flush=True)
            record["qemu_pid"] = process.pid
            (D / 'output/session.json').write_text(json.dumps({"qemu_pid": process.pid,
                "output": str(output), "control_port": control_port, "viewer_url":viewer_url,"qemu":str(qemu),"kernel":CONFIG['kernel'],"config":str(args.config.resolve()),"state": "running"}, indent=2))
            try:
                record["qemu_exit_status"] = process.wait(timeout=args.seconds)
            except subprocess.TimeoutExpired:
                record["host_timeout"] = True
                process.terminate()
                record["qemu_exit_status"] = process.wait(timeout=15)
            except BaseException:
                process.terminate()
                process.wait(timeout=15)
                raise
        record["elapsed_seconds"] = round(time.monotonic() - start, 3)
        record["nbd"] = [s.stats for s in servers]
    text = (output / "serial.log").read_text(encoding="utf8", errors="replace")
    record["observations"] = {k: v in text for k, v in {
        "bootstrap": "ANDROID_BENCH_BEGIN", "root_mounted": "ANDROID_ROOT_OVERLAY_READY",
        "original_shell": "ORIGINAL_ANDROID_SHELL_EXIT=0", "init_first_stage": "init first stage started",
        "init_second_stage": "init second stage started", "observer": "ANDROID_OBSERVER_BEGIN",
        "boot_completed": "BENCH_BOOT_COMPLETED=1"}.items()}
    record["visual_ui_observed"] = False
    if args.mode=='graphics':
        record['display_transport']=viewer.state if viewer else None
        record['live_viewer_url']=viewer_url
    record['kernel_panic'] = 'Kernel panic - not syncing:' in text
    record['system_server_process_observed'] = bool(re.search(r'^system\s+\d+\s+\d+\s+.*\bsystem_server\s*$', text, re.M))
    record['system_server_java_entered'] = 'Entered the Android system server!' in text
    record['wait_for_display_observed'] = 'WaitForDisplay' in text
    record['service_states_observed'] = {}
    for name, state in re.findall(r'\[init\.svc\.([^\]]+)\]: \[([^\]]+)\]', text):
        record['service_states_observed'].setdefault(name, [])
        if state not in record['service_states_observed'][name]:
            record['service_states_observed'][name].append(state)
    record['process_lines'] = [line for line in text.splitlines()
        if re.search(r'^\S+\s+\d+\s+\d+\s+.*\s(?:system_server|zygote64|zygote|servicemanager|hwservicemanager|logd)$', line)]
    if record['observations']['boot_completed']:
        record['boot_level'] = 'boot_completed_property_observed_no_visual_claim'
    elif record['system_server_java_entered']:
        record['boot_level'] = 'system_server_started_boot_incomplete'
    elif record['observations']['init_second_stage']:
        record['boot_level'] = 'android_init_second_stage'
    elif record['observations']['original_shell']:
        record['boot_level'] = 'firmware_userspace_shell_only'
    else:
        record['boot_level'] = 'bootstrap_failed'
    (D / 'output/session.json').write_text(json.dumps({"qemu_pid": process.pid,
        "output": str(output), "control_port": control_port, "viewer_url":viewer_url,"qemu":str(qemu),"kernel":CONFIG['kernel'],"config":str(args.config.resolve()),"state": "ended"}, indent=2))
    (output / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    (D / "output/latest.json").write_text(json.dumps({"output": str(output)}, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ["qemu_exit_status", "host_timeout", "elapsed_seconds", "observations"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
