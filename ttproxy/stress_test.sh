#!/bin/sh
# No-reflash autostart hook.  /data/stress_test.sh
# S60face-recg runs this at boot; we use it to launch ttproxy.
# If you also deploy the Tailscale bundle, merge both start lines into this file.
[ -x /data/ttproxy/run.sh ] && /data/ttproxy/run.sh &
