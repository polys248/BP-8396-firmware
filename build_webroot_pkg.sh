#!/bin/bash
# Build a webflash web-UI package (.tgz) from webroot-src. Deploy it either by
# browser-uploading at http://<device>:8090/ (auto-detected, no reboot) or via the
# OTA manifest's "ui" object.
#
# The package version (.uiver) is a CONTENT HASH of webroot-src, so a package and a
# firmware bundle built from the same webroot-src carry the identical version. An
# optional human label is stored alongside in .uilabel (informational, not gating).
#
# USAGE (WSL): bash /mnt/c/Users/Isaac/fw-tools/build_webroot_pkg.sh [LABEL]
set -euo pipefail
T=/mnt/c/Users/Isaac/fw-tools
SRC=$T/webroot-src
LABEL="${1:-}"
OUT=/mnt/c/Users/Isaac/fw-v923/ui
[ -d "$SRC" ] || { echo "ERROR: missing $SRC"; exit 1; }
mkdir -p "$OUT"

HASH=$(bash "$T/ui_hash.sh" "$SRC")

STG=$(mktemp -d)
trap 'rm -rf "$STG"' EXIT
cp -a "$SRC/." "$STG/"
rm -rf "$STG/data"                 # never ship the writable runtime subdir
echo "$HASH" > "$STG/.uiver"       # gating version = content identity
[ -n "$LABEL" ] && echo "$LABEL" > "$STG/.uilabel"

NAME="webroot-${LABEL:+$LABEL-}$HASH"
TGZ="$OUT/$NAME.tgz"
tar czf "$TGZ" -C "$STG" .
MD5=$(md5sum "$TGZ" | awk '{print $1}')
SZ=$(stat -c%s "$TGZ")

echo "built: $TGZ"
echo "  version (.uiver content-hash): $HASH"
[ -n "$LABEL" ] && echo "  label   : $LABEL"
echo "  size    : $SZ bytes"
echo "  md5     : $MD5"
echo "  files   : $(tar tzf "$TGZ" | grep -cv '/$')"
echo "  index.html present: $(tar tzf "$TGZ" | grep -c '^\./index.html$')"
echo
echo "OTA manifest 'ui' object to publish (version MUST equal the content hash):"
echo "  \"ui\": { \"update\": true, \"version\": \"$HASH\", \"url\": \"<signed-url>\", \"md5\": \"$MD5\" }"
