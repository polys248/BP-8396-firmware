#!/bin/sh
# /data/chisel/run.sh -- launch the chisel reverse-tunnel agent (guarded, mem-capped).
CFG=/data/chisel/config
[ -f "$CFG" ] || exit 0
. "$CFG"
[ "$ENABLED" = "1" ] || { echo "chisel disabled" ; exit 0; }
[ -n "$CHISEL_HUB" ] && [ -n "$CHISEL_PORT" ] || { echo "chisel: HUB/PORT unset"; exit 0; }
pidof chisel >/dev/null 2>&1 && exit 0        # already running

BIN=/data/chisel/chisel
[ -x /usr/bin/chisel ] && BIN=/usr/bin/chisel

export GOMEMLIMIT="${CHISEL_MEM_MIB:-16}MiB"
export GOGC=20

FP=""; [ -n "$CHISEL_FINGERPRINT" ] && FP="--fingerprint $CHISEL_FINGERPRINT"
AU=""; [ -n "$CHISEL_AUTH" ] && AU="--auth $CHISEL_AUTH"

# R:127.0.0.1:<port>:127.0.0.1:23  -> hub exposes our telnet on the HUB's localhost only
exec "$BIN" client --keepalive 25s --max-retry-count -1 $FP $AU \
     "$CHISEL_HUB" "R:127.0.0.1:${CHISEL_PORT}:127.0.0.1:23"
