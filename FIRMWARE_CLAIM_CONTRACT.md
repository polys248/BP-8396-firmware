# Firmware ⇄ bettapay provisioning contract (please confirm/correct)

The firmware will implement the TOFU claim flow exactly as specified. Below is the
precise wire behavior it will use. Confirm the **paths**, **JSON field names**, and
**status codes**, and provide the **fleet token** + **SN source** (bottom). Anything
marked «assumed» is my default — tell me if yours differs and it's a 1-line change.

## Tokens
- fleet token  : baked read-only `/etc/bpa/fleet_token` (same on every image).
- device token : `/data/device_token` (written by claim; survives reboot + OTA).
- tunnel token : `/data/bpagent/tunnel_token` (written by remote-enroll).
- API base     : `https://api.bettapay.ng/functions/v1` «assumed»

## 1. device-claim   (only while /data/device_token is empty)
```
POST {API_BASE}/device-claim
Authorization: Bearer <FLEET_TOKEN>
Content-Type: application/json

{"sn":"<SN>"}
```
Responses the firmware handles:
- `200` body `{"token":"<device_token>"}`   «assumed field name `token`»  → persist atomically, stop claiming.
- `404`  → heartbeat not yet registered; retry every 60 s.
- `409`  → already claimed by another identity → write claim_fault, STOP, surface status (no retry).
- other 4xx/5xx → exponential backoff retry.

## 2. remote-enroll   (bpagent, after claim)
```
POST {API_BASE}/remote-enroll
Authorization: Bearer <DEVICE_TOKEN>
Content-Type: application/json

{"sn":"<SN>", "upload_token":"<per-device LAN upload token>"}
```
- `upload_token` (NEW): the device's per-device browser-upload credential for its LAN
  `:8090` firmware page. webflash generates it zero-touch at first boot (random, unique
  per unit; no shared default is baked). bpagent sends it on **every** enroll (omitted
  only if not yet generated), so it is idempotent-upsert: **store it against the SN**
  (e.g. `device_remote.upload_token`) and **surface it to operators in the dashboard,
  keyed by SN**. A regenerated token (after a `/data` wipe) arrives on the next enroll
  and overwrites the stored one. Treat it as a secret (operator-only, not public).
- `200` body `{"token":"<tunnel_token>"}`  «assumed field `token`»; optional `{"hub":"wss://..."}` to override the baked HUB.  → persist tunnel token, connect hub.
- `401/403` → enroll rejected → **device token is NOT cleared** (clearing it would
  409-brick the unit on re-claim). bpagent keeps the device token, sets status, and
  backs off ≥ rate floor. 403 = remote access disabled by admin; 401 = transient/server.
- `404/429` → keep device token, back off ≥ rate floor. other → backoff.

### enroll 200 body — fields the agent honors (SERVER-AUTHORITATIVE)
- `token` (required) → tunnel token.
- `hub` → overrides the baked HUB.
- `allow_ports` (JSON array of ints) → **replaces** the tunnelable port allowlist and is
  **persisted** on the device; it is the source of truth, not the baked config. Send the
  full set you want enforced (e.g. `[23,443,8090]`) on every enroll.
- `tls_ports` (JSON array of ints, optional) → ports the agent reaches **over TLS** and
  relays as plaintext over the tunnel. Persisted. Device default `[443]`; send to change.

**The agent re-enrolls on every boot** and applies whatever `allow_ports`/`tls_ports`/`hub`
you return — so an allowlist change takes effect fleet-wide on the units' next boot (or
next re-enroll) with **no per-unit hand edit**. The device's baked/seeded `ALLOW_PORTS` is
only a pre-first-enroll bootstrap; after the first successful enroll the server's values are
persisted (`/data/bpagent/allow_ports`, `/data/bpagent/tls_ports`) and win across reboots,
even if a later boot-time enroll is briefly unreachable. If the backend is down at boot and a
cached tunnel token exists, the agent connects with the last persisted allowlist rather than
reverting to the baked seed.

## 3. hub connect + sessions (bpagent)
```
GET  wss://remote.bettapay.ng/agent?sn=<SN>&token=<TUNNEL_TOKEN>     (Upgrade: websocket)
```
- `401/403` → tunnel token stale → delete `/data/bpagent/tunnel_token`, re-enroll.

**Web UI port = 443 (decided).** The device UI is HTTPS-only: `:80` returns a 301 to
`https://` and ignores `X-Forwarded-Proto`, so proxying plaintext to `:80` loops. The
**agent terminates TLS to `127.0.0.1:443`** (loopback, self-signed → cert not verified)
and bridges plaintext over the session. So:
- Point the hub's `/proxy` at **port 443** for the web UI — and keep sending **plain
  HTTP** over the tunnel exactly as today; the agent does the TLS leg. No `/proxy` logic
  change beyond the target port.
- Set the hub + default allowlist to **`23,443,8090`** (443 replaces 80; 80 is useless —
  redirect-only). webflash upload stays plain HTTP on 8090; telnet on 23.
- `tls_ports` defaults to `[443]`, so no enroll-response change is needed for this.

## 4. fw-manifest (webflash OTA poll) — bearer switches to device token post-claim
```
GET {API_BASE}/fw-manifest?sn=<SN>&ver=<cur>&model=n7v9_p1
Authorization: Bearer <DEVICE_TOKEN if present else FLEET_TOKEN>
```
(unchanged otherwise from the OTA spec already deployed)

## Guarantees the firmware provides
- Fleet token lives only in the read-only image; the per-device token in writable /data.
- Once `/data/device_token` exists, the fleet token is **never sent again** (daemons
  ignore `/etc/bpa/fleet_token`), so a physically-extracted fielded unit yields only its
  own credential.
- Atomic persist (temp+fsync+rename) before first use → a crash mid-claim can't strand it.
- `409` is treated as a provisioning fault (status surfaced), not a retry loop.

## NEED FROM YOU to build + bake
1. **Confirm §1–§4** paths, request bodies, and that the success field is `token`
   (if it's e.g. `device_token`/`tunnel_token`/`access_token`, tell me the exact names).
2. **Fleet token value** to bake into `/etc/bpa/fleet_token` (or say "ship a placeholder
   and we'll set it" — but then units aren't truly zero-touch until it's set).
3. **SN source on the device** — where the firmware should read the serial. Run on a unit:
   `sqlite3 /data/user.db "select key,value from sysinfo where value like 'SV-%' or value like '%8396H%';"`
   and paste the key → I'll read SN from there (with a config override as fallback).
4. Confirm the "attendance gateway heartbeat" = aio's existing reader-gateway keepalive
   (firmware does NOT send a separate heartbeat; claim just retries on 404 until it lands).
