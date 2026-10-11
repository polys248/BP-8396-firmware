#!/bin/bash
# Tier-1b modified rootfs: aio China-URL patch + baked-in hardening
# (ttproxy + webflash binaries + /etc/init.d/S61hardening) + /etc/fw_build.
set -e
cd /root
rm -rf fw1b && mkdir fw1b && cd fw1b
cp /mnt/c/Users/Isaac/fw-v923/extract/root_sq__rootfs_squashfs.img stock.img
unsquashfs -n -d mod stock.img >/dev/null
echo "unpacked: $(find mod | wc -l) entries"

echo "=== patch aio ==="
python3 /mnt/c/Users/Isaac/fw-tools/patch_aio.py mod/usr/bin/aio

echo "=== bake in service binaries ==="
cp /mnt/c/Users/Isaac/fw-tools/ttproxy/ttproxy                 mod/usr/bin/ttproxy
cp /mnt/c/Users/Isaac/fw-tools/hardened/webflash/webflash      mod/usr/bin/webflash
chmod 755 mod/usr/bin/ttproxy mod/usr/bin/webflash
echo "ttproxy  $(stat -c%s mod/usr/bin/ttproxy) bytes"
echo "webflash $(stat -c%s mod/usr/bin/webflash) bytes"

echo "=== install /etc/init.d/S61hardening (strip CR) ==="
sed 's/\r$//' /mnt/c/Users/Isaac/fw-tools/hardened/S61hardening > mod/etc/init.d/S61hardening
chmod 755 mod/etc/init.d/S61hardening
head -1 mod/etc/init.d/S61hardening; echo "lines: $(wc -l < mod/etc/init.d/S61hardening)"

echo "=== fw_build marker ==="
echo "A3-8396 hardened tier1b aio-patch+baked-services $(date -u +%Y%m%dT%H%M%SZ)" > mod/etc/fw_build
cat mod/etc/fw_build

echo "=== repack (xz 128K all-root, no -no-xattrs) ==="
mksquashfs mod rootfs_t1b.img -comp xz -b 131072 -noappend -all-root -quiet
echo "built: $(stat -c%s rootfs_t1b.img) bytes   flags(0x18, want c000): $(xxd -s 0x18 -l2 -p rootfs_t1b.img)"

echo "=== verify via mount ==="
mkdir -p mnt
if mount -t squashfs -o loop rootfs_t1b.img mnt 2>/dev/null; then
  echo "fw_build : $(cat mnt/etc/fw_build)"
  echo "aio China url (want 0): $(strings mnt/usr/bin/aio | grep -c 119.23.124.50 || true)"
  echo "S61hardening exec: $(test -x mnt/etc/init.d/S61hardening && echo yes || echo NO)"
  echo "ttproxy present : $(test -f mnt/usr/bin/ttproxy && echo yes || echo NO)"
  echo "webflash present: $(test -f mnt/usr/bin/webflash && echo yes || echo NO)"
  sh -n mnt/etc/init.d/S61hardening && echo "S61hardening syntax OK" || echo "S61hardening SYNTAX ERROR"
  umount mnt
else
  echo "(no loop mount; skipping)"
fi

cp rootfs_t1b.img /mnt/c/Users/Isaac/fw-v923/rootfs_t1b.img
echo "copied out; md5:"; md5sum rootfs_t1b.img
