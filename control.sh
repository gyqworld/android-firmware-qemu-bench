#!/system/bin/sh
echo BENCH_CONTROL_START >/dev/ttyAMA0
while :; do
    for name in /sys/class/virtio-ports/*/name; do
        if [ "$(/system/bin/cat "$name" 2>/dev/null)" = bench.control ]; then
            port=${name%/name}
            port=/dev/${port##*/}
            echo "BENCH_CONTROL_PORT=$port" >/dev/ttyAMA0
            exec 3<>"$port"
            while :; do
                if IFS= read -r command <&3; then
                    eval "$command" >&3 2>&3
                else
                    /system/bin/sleep 1
                fi
            done
        fi
    done
    /system/bin/sleep 1
done
