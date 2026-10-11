#!/bin/sh
# Cross-compile bpagent for the A3-8396 (ARMv7, static). Run from WSL.
#   sh build.sh [buildID]
# GO defaults to ~/goroot/bin/go (the toolchain installed for this project);
# override with GO=/path/to/go. buildID defaults to bpa-<UTCdate>-<git short>.
set -e
cd "$(dirname "$0")"
GO="${GO:-$HOME/goroot/bin/go}"
BUILDID="${1:-bpa-$(date -u +%Y%m%d)-$(git rev-parse --short HEAD 2>/dev/null || echo nogit)}"
export GOOS=linux GOARCH=arm GOARM=7 CGO_ENABLED=0
"$GO" build -trimpath -ldflags="-s -w -X main.buildID=$BUILDID" -o bpagent .
echo "built bpagent buildID=$BUILDID"
file bpagent
if strings -a bpagent | grep -qF "$BUILDID"; then
  echo "stamp embedded OK"
else
  echo "STAMP MISSING"; exit 1
fi
