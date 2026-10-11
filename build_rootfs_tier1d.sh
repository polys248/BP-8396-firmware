#!/bin/bash
# Tier-1d rootfs: aio China-URL patch; baked ttproxy v2 + webflash (device-token
# OTA bearer) + bpagent (TOFU claim/serve); EMPTY /etc/bpa/fleet_token slot
# (provisioning dormant until a fleet token is provided); S61hardening runs
# `bpagent claim` + (if ENABLED) `bpagent serve`.
set -e
cd /root
rm -rf fw1d && mkdir fw1d && cd fw1d
cp /mnt/c/Users/Isaac/fw-v923/extract/root_sq__rootfs_squashfs.img stock.img
unsquashfs -n -d mod stock.img >/dev/null
echo "unpacked: $(find mod | wc -l) entries"

echo "=== patch aio ==="
python3 /mnt/c/Users/Isaac/fw-tools/patch_aio.py mod/usr/bin/aio

echo "=== bake service binaries ==="
cp /mnt/c/Users/Isaac/fw-tools/ttproxy/ttproxy            mod/usr/bin/ttproxy
cp /mnt/c/Users/Isaac/fw-tools/hardened/webflash/webflash mod/usr/bin/webflash
cp /mnt/c/Users/Isaac/fw-tools/bpagent/bpagent            mod/usr/bin/bpagent
chmod 755 mod/usr/bin/ttproxy mod/usr/bin/webflash mod/usr/bin/bpagent

echo "=== fleet token slot (EMPTY = provisioning dormant) ==="
mkdir -p mod/etc/bpa
: > mod/etc/bpa/fleet_token
chmod 644 mod/etc/bpa/fleet_token

echo "=== S61hardening ==="
sed 's/\r$//' /mnt/c/Users/Isaac/fw-tools/hardened/S61hardening > mod/etc/init.d/S61hardening
chmod 755 mod/etc/init.d/S61hardening
sh -n mod/etc/init.d/S61hardening && echo "S61 syntax OK" || echo "S61 SYNTAX ERROR"

echo "=== bundle web UI (rootfs -> /data via S61 deploy_webroot) ==="
rm -rf mod/usr/share/bettapay-webroot
mkdir -p mod/usr/share/bettapay-webroot
cp -a /mnt/c/Users/Isaac/fw-tools/webroot-src/. mod/usr/share/bettapay-webroot/
UIHASH=$(bash /mnt/c/Users/Isaac/fw-tools/ui_hash.sh /mnt/c/Users/Isaac/fw-tools/webroot-src)
echo "$UIHASH" > mod/usr/share/bettapay-webroot/.uiver          # content-hash = version
echo "tier1d-$(date -u +%Y%m%d%H%M%S)" > mod/usr/share/bettapay-webroot/.uilabel
echo "webroot files: $(find mod/usr/share/bettapay-webroot -type f | wc -l)  uiver(hash): $UIHASH"

echo "=== fw_build ==="
echo "A3-8396 hardened tier1d aio-patch+services+TOFU-claim $(date -u +%Y%m%dT%H%M%SZ)" > mod/etc/fw_build
cat mod/etc/fw_build

echo "=== repack ==="
mksquashfs mod rootfs_t1d.img -comp xz -b 131072 -noappend -all-root -quiet
echo "built: $(stat -c%s rootfs_t1d.img) bytes  flags: $(xxd -s 0x18 -l2 -p rootfs_t1d.img)"

echo "=== verify ==="
mkdir -p mnt
if mount -t squashfs -o loop rootfs_t1d.img mnt 2>/dev/null; then
  echo "fw_build: $(cat mnt/etc/fw_build)"
  echo "aio China url (want 0): $(strings mnt/usr/bin/aio | grep -c 119.23.124.50 || true)"
  for b in ttproxy webflash bpagent; do echo "$b: $(test -x mnt/usr/bin/$b && echo ok || echo MISSING)"; done
  echo "fleet slot bytes (want 0): $(stat -c%s mnt/etc/bpa/fleet_token)"
  echo "S61 claim: $(grep -c 'bpagent claim' mnt/etc/init.d/S61hardening)  serve: $(grep -c 'bpagent serve' mnt/etc/init.d/S61hardening)"
  umount mnt
fi
cp rootfs_t1d.img /mnt/c/Users/Isaac/fw-v923/rootfs_t1d.img
echo "md5:"; md5sum rootfs_t1d.img
