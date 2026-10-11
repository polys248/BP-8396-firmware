#!/bin/sh
# Start ttproxy (HTTP->HTTPS reverse proxy).  /data/ttproxy/run.sh
DIR=/data/ttproxy
LOG="$DIR/ttproxy.log"
[ -x "$DIR/ttproxy" ] || { echo "ttproxy missing" >> "$LOG"; exit 1; }
if pidof ttproxy >/dev/null 2>&1; then
    echo "[ttproxy $(date)] already running" >> "$LOG"
    exit 0
fi
chmod +x "$DIR/ttproxy" 2>/dev/null
cd "$DIR"
echo "[ttproxy $(date)] starting" >> "$LOG"
./ttproxy "$DIR/config" >> "$LOG" 2>&1 &
