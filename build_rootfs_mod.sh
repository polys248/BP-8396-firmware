#!/bin/bash
# Build the Tier-1 modified rootfs: patch aio China URL + add /etc/fw_build marker.
set -e
cd /root
rm -rf fwbuild && mkdir fwbuild && cd fwbuild
cp /mnt/c/Users/Isaac/fw-v923/extract/root_sq__rootfs_squashfs.img stock.img
unsquashfs -n -d mod stock.img >/dev/null
echo "unpacked: $(find mod | wc -l) entries"

echo "=== patch aio ==="
python3 /mnt/c/Users/Isaac/fw-tools/patch_aio.py mod/usr/bin/aio

echo "=== fw_build marker ==="
echo "A3-8396 hardened tier1 aio-patch $(date -u +%Y%m%dT%H%M%SZ)" > mod/etc/fw_build
cat mod/etc/fw_build

echo "=== repack (recipe: xz 128K all-root, NO -no-xattrs) ==="
mksquashfs mod rootfs_hardened.img -comp xz -b 131072 -noappend -all-root -quiet
echo "built: $(stat -c%s rootfs_hardened.img) bytes"
echo "superblock flags (offset 0x18, want c0 00):"
xxd -s 0x18 -l 2 rootfs_hardened.img

echo "=== verify patch in repacked image (mount) ==="
mkdir -p mnt
if mount -t squashfs -o loop rootfs_hardened.img mnt 2>/dev/null; then
  echo "mounted OK"
  echo "fw_build: $(cat mnt/etc/fw_build)"
  echo "aio China-URL occurrences (want 0): $(strings mnt/usr/bin/aio | grep -c 119.23.124.50 || true)"
  echo "aio inert-URL present: $(strings mnt/usr/bin/aio | grep -c 127.0.0.1/disabled || true)"
  umount mnt
else
  echo "(loop mount unavailable in this WSL kernel; verifying via unsquashfs instead)"
  rm -rf chk && unsquashfs -n -d chk rootfs_hardened.img >/dev/null
  echo "fw_build: $(cat chk/etc/fw_build)"
  echo "aio China-URL occurrences (want 0): $(strings chk/usr/bin/aio | grep -c 119.23.124.50 || true)"
  echo "aio inert-URL present: $(strings chk/usr/bin/aio | grep -c 127.0.0.1/disabled || true)"
fi

cp rootfs_hardened.img /mnt/c/Users/Isaac/fw-v923/rootfs_hardened.img
echo "=== copied to C:\\Users\\Isaac\\fw-v923\\rootfs_hardened.img ==="
md5sum rootfs_hardened.img
