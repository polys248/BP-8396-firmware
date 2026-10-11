#!/bin/bash
# Tier-1c rootfs: aio China-URL patch + baked services (ttproxy v2, webflash v2,
# bpagent) + /etc/init.d/S61hardening (launches all three) + /etc/fw_build.
set -e
cd /root
rm -rf fw1c && mkdir fw1c && cd fw1c
cp /mnt/c/Users/Isaac/fw-v923/extract/root_sq__rootfs_squashfs.img stock.img
unsquashfs -n -d mod stock.img >/dev/null
echo "unpacked: $(find mod | wc -l) entries"

echo "=== patch aio ==="
python3 /mnt/c/Users/Isaac/fw-tools/patch_aio.py mod/usr/bin/aio

echo "=== bake in service binaries (ttproxy v2, webflash v2, bpagent) ==="
cp /mnt/c/Users/Isaac/fw-tools/ttproxy/ttproxy            mod/usr/bin/ttproxy
cp /mnt/c/Users/Isaac/fw-tools/hardened/webflash/webflash mod/usr/bin/webflash
cp /mnt/c/Users/Isaac/fw-tools/bpagent/bpagent            mod/usr/bin/bpagent
chmod 755 mod/usr/bin/ttproxy mod/usr/bin/webflash mod/usr/bin/bpagent
for b in ttproxy webflash bpagent; do echo "$b $(stat -c%s mod/usr/bin/$b)"; done

echo "=== install /etc/init.d/S61hardening ==="
sed 's/\r$//' /mnt/c/Users/Isaac/fw-tools/hardened/S61hardening > mod/etc/init.d/S61hardening
chmod 755 mod/etc/init.d/S61hardening
sh -n mod/etc/init.d/S61hardening && echo "S61hardening syntax OK" || echo "S61hardening SYNTAX ERROR"

echo "=== fw_build marker ==="
echo "A3-8396 hardened tier1c aio-patch+ttproxyv2+webflashv2+bpagent $(date -u +%Y%m%dT%H%M%SZ)" > mod/etc/fw_build
cat mod/etc/fw_build

echo "=== repack ==="
mksquashfs mod rootfs_t1c.img -comp xz -b 131072 -noappend -all-root -quiet
echo "built: $(stat -c%s rootfs_t1c.img) bytes  flags(0x18 want c000): $(xxd -s 0x18 -l2 -p rootfs_t1c.img)"

echo "=== verify via mount ==="
mkdir -p mnt
if mount -t squashfs -o loop rootfs_t1c.img mnt 2>/dev/null; then
  echo "fw_build: $(cat mnt/etc/fw_build)"
  echo "aio China url (want 0): $(strings mnt/usr/bin/aio | grep -c 119.23.124.50 || true)"
  for b in ttproxy webflash bpagent; do echo "$b present: $(test -x mnt/usr/bin/$b && echo yes || echo NO)"; done
  echo "S61 launches bpagent: $(grep -c 'bpagent' mnt/etc/init.d/S61hardening)"
  umount mnt
fi

cp rootfs_t1c.img /mnt/c/Users/Isaac/fw-v923/rootfs_t1c.img
echo "copied out; md5:"; md5sum rootfs_t1c.img
