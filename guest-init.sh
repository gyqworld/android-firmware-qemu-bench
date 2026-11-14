#!/bin/sh
B=/bin/busybox
$B --install -s /bin
export PATH=/bin:/sbin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t tmpfs tmpfs /dev
mknod /dev/console c 5 1
mknod /dev/null c 1 3
chmod 666 /dev/null
mdev -s
exec </dev/console >/dev/console 2>&1
echo ANDROID_BENCH_BEGIN
uname -a
cat /proc/cmdline
cat /proc/partitions
mkdir -p /lower/system /lower/vendor /lower/data /rw /android
syslower=
vendorlower=
datalower=
for disk in /dev/vd?; do
    name=${disk##*/}
    [ "$(cat /sys/block/$name/serial 2>/dev/null)" = bench-data ] && continue
    [ "$(cat /sys/block/$name/serial 2>/dev/null)" = bench-apk ] && continue
    mkdir -p /lower/$name
    mount -t ext4 -o ro,noload "$disk" /lower/$name || continue
    if [ -f /lower/$name/init ] && [ -d /lower/$name/system ]; then
        syslower=/lower/$name
    elif [ -d /lower/$name/lib64/hw ]; then
        vendorlower=/lower/$name
    else
        datalower=/lower/$name
    fi
done
echo "IMAGE_MAPPING system=$syslower vendor=$vendorlower data=$datalower"
[ -n "$syslower" ] && [ -n "$vendorlower" ] || { echo IMAGE_MAPPING_FAILED; poweroff -f; }
mount -t tmpfs -o size=1536m tmpfs /rw
mkdir -p /rw/system /rw/swork /rw/vendor /rw/vwork /rw/data /rw/dwork
mount -t overlay overlay -o lowerdir=$syslower,upperdir=/rw/system,workdir=/rw/swork /android || { echo ROOT_OVERLAY_FAILED; poweroff -f; }
echo LOWER_AND_OVERLAY_LIST
ls -la "$syslower" /android
mkdir -p /android/data /android/proc /android/sys /android/dev
mkdir -p /android/vendor /android/bench /android/lib
mount -t overlay overlay -o lowerdir=$vendorlower,upperdir=/rw/vendor,workdir=/rw/vwork /android/vendor || { echo VENDOR_OVERLAY_FAILED; poweroff -f; }
if [ -n "$datalower" ]; then
    mount -t overlay overlay -o lowerdir=$datalower,upperdir=/rw/data,workdir=/rw/dwork /android/data
else
    mount -t tmpfs -o size=512m tmpfs /android/data
fi
cp /bin/busybox /android/bench/busybox
cp /lib/ld-musl-aarch64.so.1 /android/lib/ld-musl-aarch64.so.1
cp /bench/* /android/bench/
echo ANDROID_ROOT_OVERLAY_READY
mount -t proc proc /android/proc
mount -t sysfs sysfs /android/sys
mount -o bind /dev /android/dev
echo ORIGINAL_ANDROID_SHELL_BEGIN
ls -l /android/system/bin/sh /android/system/bin/linker64 /android/init
chroot /android /system/bin/sh -c 'echo ORIGINAL_ANDROID_SHELL; /system/bin/id; /system/bin/uname -a; /system/bin/ls /system/framework/framework.jar /vendor/lib64/hw/hwcomposer.drm.so'
echo ORIGINAL_ANDROID_SHELL_EXIT=$?
mode=$(cat /bench/mode)
if [ "$mode" = graphics ]; then
    for node in /sys/block/vd*/serial; do
        if [ "$(cat "$node")" = bench-data ]; then
            disk=${node%/serial};disk=/dev/${disk##*/}
            if ! blkid "$disk" | grep -q 'TYPE="ext4"'; then
                chroot /android /system/bin/mke2fs -t ext4 -O ^metadata_csum,^64bit -m 0 "$disk" || { echo BENCH_DATA_FORMAT_FAILED; poweroff -f; }
            fi
            umount /android/data
            mount -t ext4 -o noatime "$disk" /android/data || { echo BENCH_DATA_MOUNT_FAILED; poweroff -f; }
            mkdir -p /android/data/local/tmp /android/data/cache
            chmod 0777 /android/data/local/tmp
            echo BENCH_PERSISTENT_EXT4_DATA_READY
        fi
    done
    for node in /sys/block/vd*/serial; do
        if [ "$(cat "$node")" = bench-apk ]; then
            existing=false
            for installed in /android/data/app/com.autonavi.amapauto-*/base.apk; do [ -f "$installed" ] && existing=true; done
            [ "$existing" = true ] && continue
            disk=${node%/serial};disk=/dev/${disk##*/}
            mkdir -p /android/data/app/bench-amap
            dd if="$disk" of=/android/data/app/bench-amap/base.apk bs=1048576
            truncate -s "$(cat /bench/apk-bytes)" /android/data/app/bench-amap/base.apk
            chmod 0755 /android/data/app/bench-amap
            chmod 0644 /android/data/app/bench-amap/base.apk
            chown -R 1000:1000 /android/data/app/bench-amap
            echo BENCH_AMAP_STAGED_FOR_PACKAGE_SCAN
        fi
    done
fi
if [ "$mode" = probe ]; then
    echo ANDROID_PROBE_DONE
    sync
    poweroff -f
    while :; do sleep 1; done
fi
# All changes below affect only the RAM-backed overlay, never the firmware files.
printf '\nimport /bench/bench.rc\n' >>/android/init.rc
# QEMU has no original UFS/efs/persist devices. Data is already mounted above.
echo '# bench: original mounts replaced by pre-mounted RAM-backed data' >/android/vendor/etc/fstab.exynosauto9
mkdir -p /android/data/cache /android/mnt/vendor/efs /android/mnt/vendor/persist
if [ "$mode" = headless ] || [ "$mode" = graphics ]; then
    # Old overlayfs does not expose lower SELinux labels correctly. Bind executable
    # trees directly from their read-only ext4 mounts; leave root/vendor etc in RAM.
    mount -o bind "$syslower/system" /android/system
    mount -o bind "$syslower/init" /android/init
    mkdir -p /rw/init-rc
    cp /android/system/etc/init/*.rc /rw/init-rc/
    # No display is being emulated. Keep hardware display failures from repeatedly
    # killing the real zygote while the framework boot is under investigation.
    if [ "$mode" = headless ]; then sed -i '/^service surfaceflinger /a\    disabled' /rw/init-rc/surfaceflinger.rc; fi
    mount -o bind /rw/init-rc /android/system/etc/init
    if [ "$mode" = headless ]; then sed -i '/^service vendor.hwcomposer-2-1 /a\    disabled' /android/vendor/etc/init/android.hardware.graphics.composer@2.1-service.rc; fi
    for dir in bin lib lib64; do
        mount -o bind "$vendorlower/$dir" /android/vendor/$dir
    done
    if [ "$mode" = graphics ]; then
        # Preserve only the core Android packages needed by an independent app.
        # Original vehicle apps otherwise crash-loop waiting for absent AGL/MCU services.
        mount -t tmpfs tmpfs /android/system/priv-app
        for app in SettingsProvider Shell MediaProvider ExternalStorageProvider DownloadProvider DefaultContainerService PackageInstaller ExtServices FusedLocation UserDictionaryProvider ContactsProvider Settings; do
            mkdir -p /android/system/priv-app/$app
            mount -o bind "$syslower/system/priv-app/$app" /android/system/priv-app/$app
        done
        mount -t tmpfs tmpfs /android/system/app
        for app in CertInstaller KeyChain ExtShared PacProcessor PrintSpooler webview CarLatinIME; do
            mkdir -p /android/system/app/$app
            mount -o bind "$syslower/system/app/$app" /android/system/app/$app
        done
        mount -t tmpfs -o mode=0755 tmpfs /android/mnt
        mkdir -p /android/mnt/vendor /android/mnt/user/0
        printf '\nimport /bench/display.rc\n' >>/android/init.rc
        mkdir -p /rw/egl /rw/ework /rw/hw /rw/hwork
        mount -t overlay overlay -o lowerdir=$vendorlower/lib64/egl,upperdir=/rw/egl,workdir=/rw/ework /android/vendor/lib64/egl
        mount -t overlay overlay -o lowerdir=$vendorlower/lib64/hw,upperdir=/rw/hw,workdir=/rw/hwork /android/vendor/lib64/hw
        cp /bench/lib*swiftshader.so /android/vendor/lib64/egl/
        rm /android/vendor/lib64/egl/libGLES_mali.so
        cp /bench/gralloc.bench.so /android/vendor/lib64/hw/
    fi
    mkdir -p /android/sys/fs/selinux /android/dev/pts /android/dev/socket /android/mnt/vendor
    mount -t selinuxfs selinuxfs /android/sys/fs/selinux
    if [ -f /android/vendor/etc/selinux/precompiled_sepolicy ]; then
        dd if=/android/vendor/etc/selinux/precompiled_sepolicy of=/android/sys/fs/selinux/load bs=4M || { echo BENCH_POLICY_LOAD_FAILED; poweroff -f; }
    else
        echo BENCH_POLICY_NOT_FOUND
        poweroff -f
    fi
    echo 0 >/android/sys/fs/selinux/enforce
    if [ "$mode" = graphics ]; then chroot /android /bench/seed-rng; fi
    mount -t devpts devpts /android/dev/pts
    chroot /android /system/bin/restorecon /init /dev /dev/socket /dev/pts /bench
    export INIT_SECOND_STAGE=true INIT_STARTED_AT=0 INIT_SELINUX_TOOK=0
    echo BENCH_ADAPTED_SECOND_STAGE_POLICY_PERMISSIVE
fi
echo ORIGINAL_ANDROID_INIT_EXEC
cd /
# A real root switch is required: a plain chroot leaves /android prefixes visible
# through procfs, which Android zygote rejects in its inherited-FD validation.
exec switch_root /android /init
echo ANDROID_SWITCH_ROOT_FAILED
poweroff -f
