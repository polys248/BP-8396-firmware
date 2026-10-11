Tailscale /data bundle for the A3-8396 (LomboTech N7, ARMv7, Linux 4.19.73)
Tailscale 1.104.1, static linux/arm binaries (verified SHA-256 from pkgs.tailscale.com).

WHAT'S IN ts-data-bundle.tgz (extract it with /data as the current directory):
  tailscale/tailscaled   daemon      (ELF32 ARM, ~37 MB)
  tailscale/tailscale    CLI         (ELF32 ARM, ~32 MB)
  tailscale/run.sh       launcher    (reads config, starts daemon, runs 'up')
  tailscale/config       settings    <-- edit AUTHKEY (and MODE if no kernel TUN)
  tailscale/S40tailscale init script (for the permanent/reflash path only)
  stress_test.sh         boot hook   (no-reflash autostart, see below)

SIZE NOTE: the two binaries are ~70 MB uncompressed. Confirm /data has room:
  df -h /data            (and 'free -m' for RAM; tailscaled uses ~30-50 MB RAM)
If space is tight we can UPX-compress the binaries (~60% smaller) later.

INSTALL (no reflash -- recommended first):
  1. Get the tarball onto the device and lay it out on /data:
        cd /data && tar xzf /tmp/ts-data-bundle.tgz
     (gives /data/tailscale/* and /data/stress_test.sh with exec bits set)
  2. Generate a REUSABLE pre-auth key in the Tailscale admin console
     (login.tailscale.com -> Settings -> Keys), then:
        vi /data/tailscale/config      # paste AUTHKEY, set HOSTNAME_TS, MODE
  3. Test now, without rebooting:
        /data/tailscale/run.sh
        tail -n 40 /data/tailscale/tailscaled.log
        /data/tailscale/tailscale --socket=/data/tailscale/tailscaled.sock status
     You should see the device get a 100.x.y.z tailnet IP. From your remote
     machine you can then reach the web UI at http://100.x.y.z/ and, with
     --ssh enabled, 'ssh root@100.x.y.z' over the tailnet.
  4. Reboot and confirm it comes back up on its own (via stress_test.sh).

KERNEL CHECKS (run once; decide MODE and whether exit-node is possible):
  uname -m; uname -r
  ls -l /dev/net/tun
  zcat /proc/config.gz | grep -E 'CONFIG_TUN|NF_NAT|IP_NF_IPTABLES|NFT_'
  cat /proc/sys/net/ipv4/ip_forward
  - If /dev/net/tun can't be opened / no CONFIG_TUN: set MODE="userspace".
  - Exit node or subnet routes (--advertise-exit-node / --advertise-routes)
    need kernel TUN + NF_NAT + ip_forward=1. This device ships NO iptables/nft
    and no netfilter modules, so NAT must be built into the kernel; if the grep
    above shows no NF_NAT, exit-node/subnet routing is not available without a
    kernel rebuild. Plain client access still works regardless.

PERMANENT INSTALL (later, via the rootfs repack):
  Put S40tailscale at /etc/init.d/S40tailscale (mode 0755) in the rootfs, keep
  the binaries on /data, and delete /data/stress_test.sh.

UNINSTALL:
  rm -f /data/stress_test.sh ; /data/tailscale/tailscale --socket=/data/tailscale/tailscaled.sock down ; kill $(pidof tailscaled)
