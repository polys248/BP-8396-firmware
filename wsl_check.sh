#!/bin/bash
echo "--- distro ---"
grep -E '^PRETTY' /etc/os-release 2>/dev/null || echo unknown
echo "--- tools ---"
for t in mksquashfs unsquashfs zip; do
  if command -v "$t" >/dev/null 2>&1; then
    echo "$t = $(command -v "$t")"
  else
    echo "$t = MISSING"
  fi
done
mksquashfs -version 2>&1 | head -1
echo "--- home / arch ---"
echo "HOME=$HOME"
uname -m
