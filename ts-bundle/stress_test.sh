#!/bin/sh
# No-reflash autostart hook.  Location: /data/stress_test.sh
# S60face-recg runs this in the background at every boot if it exists, which we
# borrow to launch Tailscale with zero changes to the (read-only) firmware.
# If you later bake /etc/init.d/S40tailscale into the rootfs, delete this file.
[ -x /data/tailscale/run.sh ] && /data/tailscale/run.sh &
