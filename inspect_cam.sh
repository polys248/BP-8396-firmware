#!/bin/bash
umount /mnt/rootimg 2>/dev/null
mkdir -p /mnt/rootimg
mount -o loop,ro /mnt/c/Users/Isaac/fw-v923/extract/root__rootfs.img /mnt/rootimg || { echo "mount failed"; exit 1; }
A=/mnt/rootimg/usr/bin/aio
echo "=== Snapshot / GetFile / capture / realtime strings in aio ==="
strings -n 5 "$A" | grep -iE 'Snapshot|CameraSnapshot|RealtimeImage|GetRealtime|take.?photo|capture|Preview|current.?frame|live' | sort -u | head -50
echo
echo "=== System API image endpoints ==="
strings -n 6 "$A" | grep -oE '/api/System/[A-Za-z]+' | sort -u
echo
echo "=== FileType values GetFile understands ==="
strings -n 4 "$A" | grep -iE 'BootImage|ScreenImage|Snapshot|FileType' | sort -u | head -30
echo
echo "=== any MJPEG/video HTTP path ==="
strings -n 5 "$A" | grep -iE '\.mjpeg|mjpeg_http|/video|x-mixed-replace|boundary' | sort -u | head -20
umount /mnt/rootimg 2>/dev/null
