#!/bin/bash
# Prints a stable 16-hex content hash of a webroot directory: captures every file's
# path + bytes, order-independent, excluding the generated marker files. Identical
# content -> identical hash, so the UI package and the firmware bundle built from the
# same webroot-src get the same .uiver. Usage: ui_hash.sh <webroot-dir>
set -euo pipefail
dir="$1"
[ -d "$dir" ] || { echo "ui_hash: no such dir: $dir" >&2; exit 1; }
( cd "$dir" \
  && find . -type f ! -name .uiver ! -name .uilabel -print0 \
     | LC_ALL=C sort -z \
     | xargs -0 sha256sum \
     | sha256sum | cut -c1-16 )
