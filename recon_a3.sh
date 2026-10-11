#!/bin/sh
# A3-8396 read-only recon. Safe: only reads state, changes nothing.
sec() { echo; echo "===== $* ====="; }
have() { command -v "$1" >/dev/null 2>&1; }

sec "IDENTITY"
uname -a
echo "arch: $(uname -m)   kernel: $(uname -r)"
[ -r /proc/device-tree/model ] && { echo -n "dt-model: "; tr -d '\0' </proc/device-tree/model; echo; }
[ -r /proc/device-tree/compatible ] && { echo -n "dt-compat: "; tr '\0' ' ' </proc/device-tree/compatible; echo; }
[ -r /etc/build.prop ] && grep -E 'build|chip|model|device' /etc/build.prop
echo -n "cpu: "; grep -m1 -E 'model name|Processor|Features' /proc/cpuinfo
grep -m1 Features /proc/cpuinfo

sec "MEMORY / STORAGE"
free -m 2>/dev/null || grep -E 'MemTotal|MemFree' /proc/meminfo
echo "--- df ---"; df -h 2>/dev/null
echo "--- /proc/mtd ---"; cat /proc/mtd 2>/dev/null
echo "--- mounts ---"; mount
echo "--- /data ---"; ls -la /data 2>/dev/null; df -h /data 2>/dev/null

sec "KERNEL FEATURES (TUN / NAT / forwarding / squashfs)"
echo -n "/dev/net/tun: "; ls -l /dev/net/tun 2>/dev/null || echo "ABSENT"
echo -n "ip_forward: "; cat /proc/sys/net/ipv4/ip_forward 2>/dev/null
echo "--- /proc/config.gz greps ---"
if [ -r /proc/config.gz ]; then
  zcat /proc/config.gz 2>/dev/null | grep -E 'CONFIG_TUN|NF_NAT|NETFILTER|IP_NF_IPTABLES|NFT|IP_ADVANCED_ROUTER|BRIDGE|SQUASHFS' || echo "(no matches)"
else
  echo "/proc/config.gz not present"
fi
echo "--- loaded modules ---"; lsmod 2>/dev/null
echo "--- filesystems ---"; cat /proc/filesystems 2>/dev/null | grep -E 'squash|ext|overlay|tmpfs'
echo -n "iptables: "; have iptables && iptables --version 2>/dev/null || echo "ABSENT"
echo -n "nft: "; have nft && nft --version 2>/dev/null || echo "ABSENT"
echo -n "ip: "; have ip && ip -V 2>/dev/null || echo "ABSENT"

sec "NETWORK"
ip addr 2>/dev/null | grep -E 'inet |link/ether|^[0-9]+:' || ifconfig -a
echo "--- routes ---"; ip route 2>/dev/null || route -n
echo "--- resolv.conf ---"; cat /etc/resolv.conf 2>/dev/null
echo "--- listening sockets ---"; netstat -tlnp 2>/dev/null || netstat -tln 2>/dev/null

sec "WEB UI / FLASH PATH"
echo "--- processes ---"; ps w 2>/dev/null || ps aux 2>/dev/null
echo "--- aio http/update endpoints hint (ls /data/ota, update dirs) ---"
ls -la /data/ota 2>/dev/null; ls -la /data/*.sh 2>/dev/null
echo "--- update/ota/burn tools on PATH ---"
ls /usr/bin /usr/sbin /sbin /bin 2>/dev/null | grep -iE 'ota|updat|upgrad|burn|flash|recovery' | sort -u

sec "LIVE CONFIG DB"
echo -n "/data/user.db: "; ls -l /data/user.db 2>/dev/null || echo "absent"
echo -n "/etc/user.db:  "; ls -l /etc/user.db 2>/dev/null || echo "absent"
AIO=$(pidof aio 2>/dev/null)
echo "aio pid: ${AIO:-not running}"
if [ -n "$AIO" ]; then
  echo "--- user.db file handles open by aio (which copy is LIVE) ---"
  ls -l /proc/$AIO/fd 2>/dev/null | grep -i '\.db' || echo "(none matched)"
fi
if have sqlite3; then
  echo "--- live sysinfo (network/cloud keys) ---"
  sqlite3 /data/user.db "select key||' = '||value from sysinfo where key in ('UseHTTPClient','HttpClientSwitch','HTTPClient_ServerIP','HTTPClient_ServerAddr','HTTPClient_ServerPort','HTTPClient_SSLType','UseMQTTClient','UseMQTTSSL','MQTTServerAddr','ServerAddress','tange_switch');" 2>/dev/null
else
  echo "sqlite3 CLI not present (expected); DB values already known from firmware"
fi

sec "LIVE PHONE-HOME CONNECTIONS"
netstat -tn 2>/dev/null | grep -E 'ESTAB|SYN' | grep -E '8883|9003|47\.92\.116\.62|:443' || echo "(no matching established connections right now)"

sec "DONE"
echo "recon complete"
