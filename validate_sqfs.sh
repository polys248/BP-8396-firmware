#!/bin/bash
# Validate the mksquashfs recipe faithfully round-trips the stock rootfs.
set -e
cd /root
rm -rf fwval && mkdir fwval && cd fwval
SRC=/mnt/c/Users/Isaac/fw-v923/extract/root_sq__rootfs_squashfs.img
cp "$SRC" stock.img
echo "stock size: $(stat -c%s stock.img)"

unsquashfs -n -d un stock.img >/dev/null
echo "unpacked entries: $(find un | wc -l)"

# recipe (matches reversed superblock: xz, 128K, all-root, no-xattrs, duplicates+exportable defaults)
mksquashfs un test.img -comp xz -b 131072 -noappend -all-root -no-xattrs -quiet
echo "rebuilt size: $(stat -c%s test.img)"

unsquashfs -n -d un2 test.img >/dev/null
echo "=== diff -r un vs un2 ==="
if diff -r un un2 >/tmp/sqdiff 2>&1; then
  echo "CONTENT IDENTICAL"
else
  echo "DIFFERS:"; head -40 /tmp/sqdiff
fi
# compare superblock headers
echo "=== superblock (first 96 bytes) ==="
echo "stock:"; xxd -l 96 stock.img | head -6
echo "test :"; xxd -l 96 test.img  | head -6
