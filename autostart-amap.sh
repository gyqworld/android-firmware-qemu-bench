#!/system/bin/sh
exec >/dev/ttyAMA0 2>&1
echo AMAP_AUTOSTART_BEGIN
echo BENCH_BOOT_COMPLETED=$(getprop sys.boot_completed)
settings put global device_provisioned 1
settings put secure user_setup_complete 1
settings put system screen_off_timeout 2147483647
/bench/busybox timeout -s TERM -k 2 15 svc power stayon true
/bench/busybox timeout -s TERM -k 2 15 input keyevent KEYCODE_WAKEUP
for n in 1 2 3 4 5 6; do
    if pm path com.autonavi.amapauto; then break; fi
    sleep 5
done
if ! pm path com.autonavi.amapauto; then
    echo AMAP_NOT_INSTALLED
    exit 1
fi
pm grant com.autonavi.amapauto android.permission.WRITE_EXTERNAL_STORAGE
pm grant com.autonavi.amapauto android.permission.READ_EXTERNAL_STORAGE
am set-debug-app com.autonavi.amapauto
settings put secure anr_show_background 1
am start -n com.autonavi.amapauto/com.autonavi.auto.remote.fill.UsbFillActivity
echo AMAP_START_COMMAND_EXIT=$?
sleep 10
ps -A | grep com.autonavi.amapauto
echo BENCH_BOOT_COMPLETED=$(getprop sys.boot_completed)
echo AMAP_AUTOSTART_END
