# A3-8396 provisioning — carton to fielded unit

How to take a brand-new, stock A3-8396 and bring it to the state of our test unit:
hardened prod rootfs, phone-home severed, claimed + enrolled + tunnelled, BettaPay UI,
OTA on. Decisions baked into this flow: **USB flash via PkgBurnPro** for the first
(bootstrap) flash, **manual reader registration** server-side, and the aio→ttproxy
repoint is now **automatic on first boot** (S61), so per-unit work is minimal.

> Terms: **fleet token** = shared build-time secret (baked read-only at
> `/etc/bpa/fleet_token`). **device token** = per-unit, TOFU, permanent (`/data/device_token`).
> **tunnel token** = per-unit, rotates each enroll (`/data/bpagent/tunnel_token`). The fleet
> token never leaves your machine; you build the image yourself.

---

## End state (what "like the test unit" means)
- `aio` phone-home URL binary-patched out **and** the China IPs route-blackholed.
- `aio`'s backend client pointed at **ttproxy** (`127.0.0.1:4610`), which does real HTTPS to
  `https://api.bettapay.ng` (works around the Mongoose client-TLS bug).
- **webflash** on `:8090` (browser upload) + hourly **OTA** poll.
- **bpagent**: claimed (`device_token`), enrolled (`tunnel_token`), outbound tunnel to the hub,
  ports `23,443,8090`, TLS-terminating `443` for the web UI.
- **BettaPay web UI** deployed into `/data/webpage/webroot`.

---

## Phase 0 — build the release (one-time per firmware version, on your machine)

In WSL (Go toolchain lives at `~/goroot`; `bpagent/build.sh` rebuilds the agent for ARM):

```bash
# rebuild service binaries first if their .go changed, e.g.:
sh bpagent/build.sh                                   # -> bpagent/bpagent (ARM, stamped)
# then the prod image (bakes YOUR fleet token; run as root for the loop mounts):
sudo bash build_prod_image.sh /root/prod_fleet_token prod-YYYYMMDD
shred -u /root/prod_fleet_token                       # remove the plaintext token after
```

Output in `…/fw-v923/prod/`: `n7v9_p1-<version>-<md5>.zip` containing a top-level `.fwver`
(the version). **Register the release** on the backend's OTA form — it auto-reads `.fwver`
(or parses the filename); record the md5 as the release id. This is what fielded units OTA to.

---

## Phase 1 — bootstrap flash (per unit, USB / PkgBurnPro)

A from-carton unit has none of our tooling, so the first flash can't use webflash/OTA — it's
the vendor factory path: **PkgBurnPro over USB download mode** (`vendor/PkgBurnPro_v2.3.1/`,
see its PDF guide).

⚠️ **Open item to confirm once:** `build_prod_image.sh` emits a `recovery.zip` (for the
on-device recovery path), **not** a PkgBurnPro USB package. The hardened rootfs is the
`root_sq` partition image inside that zip (`rootfs_squashfs.img`). To USB-flash it you need
that image in PkgBurnPro's package format — in practice, take the vendor's original full
firmware package and swap in our `rootfs_squashfs.img` for the `root_sq` partition, then burn.
Confirm the exact package layout against the vendor tool / PDF (or share the vendor package and
I'll script the swap). **This does not flash `/data`** — the writable partition (and its
`user.db`) is preserved, which is why the aio repoint happens at runtime, not in the image.

After the burn completes, the unit reboots into the hardened rootfs.

---

## Phase 2 — first boot (automatic, `S61hardening`)

On every boot, after `S60face-recg`, S61 runs (idempotent, survives factory reset):
1. Brings up loopback (`lo`) — the device doesn't at boot; ttproxy/aio need it.
2. Deploys the BettaPay web UI from rootfs → `/data` (only when the bundled `.uiver` changed).
3. Severs phone-home: blackholes `119.23.124.50`, `47.92.116.62`, and resolved `*.faceds.cc`;
   kills any `tange` process.
4. Writes default `/data` configs if missing (prod bakes **OTA=3600**, bpagent **ENABLED=1**,
   **ALLOW_PORTS=23,443,8090**).
5. **Repoints `aio` at ttproxy** (`/data/user.db` sysinfo → `http://127.0.0.1:4610/functions/v1/reader-gateway`)
   — one-time, idempotent, backs up `user.db` first. *(New: previously a manual step.)*
6. Starts ttproxy + webflash.
7. `bpagent claim` (if a fleet token exists and not yet claimed) → persists `device_token`.
8. `bpagent serve` (ENABLED=1) → remote-enroll → tunnel token + server `allow_ports`/`tls_ports`
   → connects the hub.

> **Timing note:** `aio` is started by S60 *before* S61 repoints it, so `aio` may keep using
> the old backend until it reconnects or the **next reboot**. `bpagent claim` retries every
> 60 s, so provisioning converges on its own — but if a unit sits at "claim 404" for a few
> minutes, **one reboot** forces `aio` to re-read the repointed address.

---

## Phase 3 — server-side registration (per unit, manual)

Before claim can succeed, the unit's **SN must be registered as a reader under its tenant**
(`attendance_readers.tenant_id`) in the back-office. This is what lets the device's
reader-gateway keepalive register (so `device-claim` stops returning 404) **and** binds the
unit to the right tenant for enrollment-sync. The enroll call also reports the unit's per-unit
LAN `upload_token`, surfaced in the dashboard keyed by SN (operator-only secret).

Find the SN on the unit if needed:
```
sqlite3 /data/user.db "select value from sysinfo where key='DeviceSN';"
```

---

## Phase 4 — verify

On the unit (telnet/root, port 23 is in the allowlist) and on the backend:

| Check | Where / command | Expect |
|---|---|---|
| Hardening ran | `cat /data/hardening.log` | `lo up`, `repointed aio -> ttproxy`, `started ttproxy/webflash`, `launched bpagent …` |
| aio repointed | `sqlite3 /data/user.db "select value from sysinfo where key='HTTPClient_ServerAddr';"` | `http://127.0.0.1:4610/functions/v1/reader-gateway` |
| Phone-home dead | `ip route \| grep -E '119.23.124.50\|47.92.116.62'` | routes via `lo`/blackhole |
| Claimed | `cat /data/bpagent/claim.log`; `test -s /data/device_token` | device token persisted |
| Enrolled + tunnel | `cat /data/bpagent/bpagent.log` | `bpagent build bpa-…`, hub connected, `session_done` lines on UI sessions |
| Services listening | `netstat -ltn \| grep -E '4610\|8090'` | ttproxy + webflash up |
| Web UI | browser `https://<unit>` (or via hub/443) | rebranded BettaPay UI loads |
| On the hub/dashboard | backend | unit online; `upload_token` shown for its SN |
| OTA | `cat /data/webflash/webflash.log` | `ota: enabled …` poll OK |

---

## Troubleshooting

- **`claim` stuck on 404** → SN not yet a registered reader (Phase 3), or `aio` not yet talking
  to BettaPay (repoint applied but `aio` hasn't re-read — reboot once). Confirm keepalives are
  arriving backend-side.
- **No tunnel** → check `ENABLED=1` in `/data/bpagent/config` and that enroll returned
  `allow_ports` incl `443`; `/data/bpagent/{allow_ports,tls_ports}` hold the server-authoritative
  set. `401/403` on hub = stale tunnel token (agent auto-re-enrolls).
- **UI stale after update** → content-hash gating; a hard refresh or confirm `.uiver` changed.
- **`409` on claim** → SN already claimed by another identity; `/data/bpagent/claim_fault`
  written, no retry — investigate before wiping (device token is permanent by design).

---

## Notes
- The **device token is permanent** — never cleared by firmware (only an admin deleting the
  server row ends it); a `/data` wipe/factory-reset keeps the baked rootfs hardening and
  re-claims cleanly.
- The **fleet token** exists only in the read-only image; once `/data/device_token` exists the
  fleet token is never sent again, so a physically-extracted unit yields only its own credential.
- To ship a unit with the tunnel **off**, build with `BP_ENABLED=0` (opt-in per device later via
  `/data/bpagent/config`).
