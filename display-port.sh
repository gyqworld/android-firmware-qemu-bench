#!/system/bin/sh
while :; do
    for name in /sys/class/virtio-ports/*/name; do
        if [ "$(cat "$name" 2>/dev/null)" = bench.display ]; then
            port=${name%/name}
            ln -sf /dev/${port##*/} /dev/bench-display
            chmod 0666 /dev/${port##*/}
            echo BENCH_DISPLAY_PORT_READY >/dev/ttyAMA0
            exit 0
        fi
    done
    sleep 1
done
