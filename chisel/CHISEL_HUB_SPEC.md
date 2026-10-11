# A3-8396 remote access — chisel hub (fleet-scale, no TUN, outbound-only)

Each device runs a `chisel client` that dials OUT to one central **hub** and
reverse-tunnels its telnet (127.0.0.1:23) to the hub's localhost. You reach any
device by SSHing to the hub and `telnet localhost <that device's port>`. Works
behind NAT / site-to-site VPN; nothing inbound needed on the device.

```
 device A ──out──▶┐
 device B ──out──▶┤   chisel hub (public IP)   ◀──SSH── you
 device C ──out──▶┘   telnet ports on 127.0.0.1
```

## 1. Stand up the hub (a small public VM — 1 vCPU / 1 GB is plenty for many clients)

Install chisel (same release, pick the host's arch, e.g. linux_amd64), then run it
with a STABLE key (so the fingerprint never changes) and reverse tunnels enabled:

```
# make a stable key once:
chisel server --keygen /etc/chisel/key.pem
# note the fingerprint it prints (or:)  chisel server --key "$(cat /etc/chisel/key.pem)" ... --pid
# run the hub (systemd unit recommended):
chisel server \
  --reverse \
  --host 0.0.0.0 --port 8080 \
  --key "$(cat /etc/chisel/key.pem)" \
  --authfile /etc/chisel/users.json \
  --keepalive 25s
```
On start it logs `Fingerprint xx:xx...` — that string goes in each device's
`CHISEL_FINGERPRINT` (pins the hub; no CA store needed on the device).

Put the hub behind your own TLS/CDN if you like, but it's optional — chisel's
channel is SSH-encrypted regardless; the fingerprint is what makes it secure.

## 2. Per-device auth + port (the fleet registry)

`/etc/chisel/users.json` — one entry per device, locked to just its own reverse port
(so a compromised unit can't grab another's tunnel). `user:pass` keyed by SN:

```json
{
  "SV-8396H26031043:<rand1>": ["R:127.0.0.1:20001"],
  "SV-8396H26031044:<rand2>": ["R:127.0.0.1:20002"]
}
```
Maintain an **SN → port** table (a DB table or a flat file) — e.g. port = 20000 +
sequential index. That table + the creds are what you provision onto each device's
`/data/chisel/config` (`CHISEL_AUTH`, `CHISEL_PORT`). For the fleet, push these the
same way as firmware config — or have the device fetch them from bettapay on first boot
keyed by its SN (nice future integration with the OTA backend you already built).

## 3. Reach a device (operator)

The reverse ports bind to the hub's **localhost** only, so they're never public:
```
ssh you@hub
telnet 127.0.0.1 20001        # device SV-...043's shell
```
Or tunnel it to your laptop:  `ssh -L 20001:127.0.0.1:20001 you@hub`  then `telnet localhost 20001`.
A tiny web/console on the hub can map SN → port and launch the session for your team.

## 4. Device side (already built)
`/data/chisel/` : `chisel` binary + `run.sh` + `config`. Set in config:
`ENABLED=1`, `CHISEL_HUB=http://<hub>:8080`, `CHISEL_FINGERPRINT=<from step 1>`,
`CHISEL_AUTH=<sn>:<pass>`, `CHISEL_PORT=<this unit's port>`. `run.sh` launches it
mem-capped and auto-reconnecting. In the hardened firmware, `S61hardening` will call
`run.sh` on boot (guarded), so every unit auto-connects.

## 5. Security notes
- SSH-encrypted tunnel + **fingerprint pin** + **per-device creds** + reverse ports
  bound to hub localhost. Rotate a unit's creds if it's compromised (edit users.json).
- Telnet is plaintext but only ever travels inside the encrypted chisel tunnel and over
  your SSH to the hub — never on the open internet.
- Longer term, swap telnet for dropbear-SSH on the device and tunnel that instead;
  and/or replace chisel with the custom SN-authenticated agent for a smaller footprint.

## 6. Scale
One hub handles hundreds of idle reverse tunnels fine (each is a cheap idle TCP/SSH
channel). Watch hub RAM/fd limits; shard to a second hub by SN range if you ever need to.
Device-side RAM is the real limit — see the note about chisel (~12–15 MB RSS) vs a
custom agent (~6 MB) if units get memory-tight.
