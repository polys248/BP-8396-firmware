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

Output in `…/fw-v923/prod/`: two artifacts from one build —
- **`n7v9_p1-<version>-<md5>.zip`** — recovery.zip (OTA / on-device recovery path), carrying a
  top-level `.fwver`. **Register this** on the backend's OTA form (it auto-reads `.fwver` or
  parses the filename); the md5 is the release id. This is what fielded units OTA to.
- **`n7v9_p2-<version>-<md5>.pkg`** — the PkgBurnPro USB package for from-carton bootstrap
  (Phase 1). Same rootfs, vendor container.

Both carry the baked fleet token, so handle them as secrets.

---

## Phase 1 — bootstrap flash (per unit, USB / PkgBurnPro)

A from-carton unit has none of our tooling, so the first flash can't use webflash/OTA — it's
the vendor factory path: **PkgBurnPro over USB download mode** (`vendor/PkgBurnPro_v2.3.1/`,
see `fw-v923/PkgBurnPro_guide.pdf`).

**The USB package is now produced by the build.** `build_prod_image.sh` (Phase 0) emits, next to
the recovery.zip, a hardened **`n7v9_p2-<version>-<md5>.pkg`** — the vendor ' PK ' container with
*only* the `root_sq` rootfs swapped for ours (`pkg_repack.py`). Every SoC binary (SPL/U-Boot/
kernel/DTB/recovery) stays byte-for-byte; offsets and the PK checksum are recomputed. Secure boot
is not enforced on this unit, so the swapped image boots. (If the vendor `.pkg` isn't on the build
machine, that step is skipped with a note — set `VENDOR_PKG=` to point at it.)

Flash it:
1. Install the vendor USB driver (`驱动文件.rar` in the firmware folder) if not already present.
2. Put the unit in USB download mode and connect it (per the PkgBurnPro PDF).
3. Open **PkgBurnPro.exe**, load `n7v9_p2-<version>-<md5>.pkg`, and burn.

This flashes the firmware partitions (incl. `root_sq`) but **not `/data`** — the writable
partition (and its `user.db`) is preserved, which is why the aio repoint happens at runtime
(Phase 2), not in the image. After the burn, the unit reboots into the hardened rootfs.

> ⚠️ **Brick-safety / validation status.** The PK format, the rootfs swap, and the checksum are
> validated (round-trips byte-identical; a swapped `.pkg` re-parses correctly), and secure boot is
> off — but a PkgBurnPro **USB flash of a swapped `.pkg` has not yet been proven on hardware**
> (the test unit was provisioned via the in-device `mtd8` reflash / `/data` path, not PkgBurnPro).
> Before relying on it for a fleet: do the **first burn on a unit you can recover**, keep the
> original vendor `n7v9_p2-…v9.23.pkg` as the golden restore image, and confirm PkgBurnPro's own
> USB-recovery works on that hardware. The device also has a `recovery` partition (mtd7) as a
> second net. Size note: our rootfs is ~46 MB against the 52 MB `root_sq` partition (~88% full) —
> watch headroom as the UI/binaries grow.

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
- **UI stale / reverted after a flash** → the served UI is in `/data/webpage/webroot`. S61
  `deploy_webroot` treats the firmware's **bundled** UI as authoritative and redeploys whenever
  the served `DST/.uiver` differs from the image's bundle, so this self-heals on the next boot on
  any image carrying that fix. To force it on a unit still running the old gate (the pre-fix
  stamp early-return could leave a stale `/data` UI), clear the markers and reboot — the runtime
  `/data` subdir is preserved:
  `rm -f /data/.bettapay_rootfs_uiver /data/webpage/webroot/.uiver && reboot`.
  Confirm `webroot deployed (<hash>)` in `/data/hardening.log`. Note: a **webflash UI hotfix does
  not survive a reboot** — the flashed image's UI wins every boot.
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
