#!/bin/sh
# /data/stress_test.sh  -- boot hook run by /etc/init.d/S60face-recg (after aio starts).
# A3-8396 hardening: (0) bring up loopback, (1) sever China phone-home,
# (2) HTTPS via ttproxy, (3) web/OTA flash daemon. All in writable /data;
# delete this file to fully revert.
LOG=/data/hardening.log
echo "=== hardening boot $(date) ===" >> "$LOG"

# ---------- (0) loopback ----------
# This device does NOT bring up lo at boot; 127.0.0.1 is required for ttproxy
# to bind and for aio to reach it. aio retries keepalives every ~5s, so doing
# this here (slightly after aio starts) is fine.
if ! ip addr show lo 2>/dev/null | grep -q '127\.0\.0\.1'; then
    ifconfig lo 127.0.0.1 netmask 255.0.0.0 up 2>/dev/null \
      || { ip addr add 127.0.0.1/8 dev lo 2>/dev/null; ip link set lo up 2>/dev/null; }
    echo "brought up lo" >> "$LOG"
fi

# ---------- (1) sever phone-home ----------
# Try blackhole route, then route-to-lo, then busybox 'route' -- whichever the
# kernel/ip build supports.  (No iptables on this kernel.)
block_ip() {
    [ -n "$1" ] || return
    ip route add blackhole "$1" 2>/dev/null && { echo "blackholed $1" >> "$LOG"; return; }
    ip route add "$1" dev lo  2>/dev/null && { echo "lo-routed $1"  >> "$LOG"; return; }
    route add -host "$1" lo   2>/dev/null && { echo "route-lo $1"   >> "$LOG"; return; }
    echo "FAILED to block $1" >> "$LOG"
}
# hardcoded VerifyData server (Aliyun Hangzhou) + faceds.cc default cloud IP
for ip in 119.23.124.50 47.92.116.62; do block_ip "$ip"; done
# resolve vendor cloud hostnames and block whatever they point to now
for host in yun.faceds.cc wc.faceds.cc faceds.cc; do
    for ip in $(nslookup "$host" 2>/dev/null | awk '/^Address[ 0-9]*:/{print $NF}' | grep -E '^[0-9]+\.'); do
        block_ip "$ip"
    done
done
# keep Tange P2P (China) disabled
for p in $(pgrep -f tange 2>/dev/null); do kill -9 "$p" 2>/dev/null && echo "killed tange $p" >> "$LOG"; done

# ---------- (2) ttproxy: local HTTP -> HTTPS to your backend ----------
if [ -x /data/ttproxy/run.sh ]; then
    /data/ttproxy/run.sh >> "$LOG" 2>&1 &
    echo "started ttproxy" >> "$LOG"
fi

# ---------- (3) web/OTA firmware-update daemon ----------
if [ -x /data/webflash/webflash ]; then
    /data/webflash/webflash >> /data/webflash/webflash.log 2>&1 &
    echo "started webflash" >> "$LOG"
fi
