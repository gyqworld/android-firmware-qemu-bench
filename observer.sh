#!/system/bin/sh
exec >/dev/ttyAMA0 2>&1
echo ANDROID_OBSERVER_BEGIN
for wait in 2 5 10 20 30 45 60; do
    /system/bin/sleep "$wait"
    echo ANDROID_SNAPSHOT_BEGIN
    /system/bin/cat /proc/uptime
    /system/bin/ls -lZ /proc/1/exe /dev/binder /dev/hwbinder /dev/vndbinder /dev/null /dev/ashmem /dev/socket /dev/kmsg
    echo BENCH_ANDROID_RELEASE=$(/system/bin/getprop ro.build.version.release)
    echo BENCH_BOOT_COMPLETED=$(/system/bin/getprop sys.boot_completed)
    /system/bin/getprop | /system/bin/grep -E 'init.svc.(zygote|servicemanager|hwservicemanager|surfaceflinger|logd|bench-control)|ro.crypto.state'
    /system/bin/ls -l /sys/class/virtio-ports /dev/vport*
    /system/bin/cat /sys/class/virtio-ports/*/name
    /system/bin/ps -A
    /system/bin/dmesg | /system/bin/grep -E 'init:|ueventd:' | /system/bin/tail -n 90
    /system/bin/logcat -b all -d -t 70
    echo ANDROID_IMPORTANT_LOGS_BEGIN
    /system/bin/logcat -b all -d -v threadtime -s AndroidRuntime:V SystemServer:V Zygote:V zygote64:W libc:F DisplayManagerService:V SurfaceFlinger:E
    /system/bin/logcat -b crash -d -t 100
    echo ANDROID_IMPORTANT_LOGS_END
    /system/bin/ls -l /data/tombstones
    echo ANDROID_SNAPSHOT_END
done
echo ANDROID_OBSERVER_END
