# A3-8396 OTA — backend spec (bettapay / Supabase)

The device's `webflash` daemon polls your backend over HTTPS. When you publish a
newer build for a device (or globally), the device downloads the `recovery.zip`,
md5-verifies it, and reboots into recovery to flash it. You "push" by publishing;
the device pulls on its interval (default hourly).

## 1. Protocol

**Request (device → backend), every `OTA_INTERVAL` seconds:**
```
GET  https://api.bettapay.ng/functions/v1/fw-manifest?sn=<SN>&ver=<current>&model=n7v9_p1
Authorization: Bearer <OTA_TOKEN>
```
- `sn` — device serial (e.g. `SV-8396H26031043`)
- `ver` — the version the device last flashed (or `none`)
- `model` — always `n7v9_p1` for this hardware

**Response:**
- **No update:** HTTP `204` (empty), or `200 {"update": false}`.
- **Update available:** HTTP `200`, JSON:
  ```json
  { "update": true, "version": "9.23.1", "url": "https://.../signed/recovery.zip", "md5": "df28f2b575a91ccceded599f24dfb77d" }
  ```
  - `version` — new version string (must differ from the device's `ver`, or it's skipped)
  - `url` — HTTPS URL to the `recovery.zip` (a short-lived Supabase signed URL is ideal)
  - `md5` — lowercase hex md5 of that exact zip. **The device refuses the file if this doesn't match**, and recovery re-verifies again before writing flash.

The device records `version` after staging, so it won't re-flash the same build. To
force a re-flash, publish a new `version` string.

## 2. Supabase setup

**Storage:** a private bucket `firmware`. Upload each build to e.g.
`n7v9_p1/<version>/update.zip`.

**Tables:**
```sql
create table firmware_releases (
  model text not null,
  version text not null,
  path text not null,     -- storage path, e.g. 'n7v9_p1/9.23.1/update.zip'
  md5 text not null,      -- lowercase hex md5 of the zip
  created_at timestamptz default now(),
  primary key (model, version)
);
create table firmware_default (            -- global target per model
  model text primary key,
  version text not null
);
create table device_targets (             -- optional per-device override
  sn text primary key,
  target_version text not null
);
```

**Edge function `fw-manifest`** (Deno/TypeScript):
```ts
import { createClient } from "jsr:@supabase/supabase-js@2";

const OTA_TOKEN = Deno.env.get("OTA_TOKEN")!;              // the fleet token (shared pre-claim secret)
const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SERVICE_ROLE_KEY")!);

Deno.serve(async (req) => {
  if (req.headers.get("authorization") !== `Bearer ${OTA_TOKEN}`)
    return new Response("unauthorized", { status: 401 });

  const u = new URL(req.url);
  const sn    = u.searchParams.get("sn")    ?? "";
  const cur   = u.searchParams.get("ver")   ?? "";
  const model = u.searchParams.get("model") ?? "n7v9_p1";

  // target = per-device override, else global default for the model
  const dev = await sb.from("device_targets").select("target_version").eq("sn", sn).maybeSingle();
  let target = dev.data?.target_version as string | undefined;
  if (!target) {
    const def = await sb.from("firmware_default").select("version").eq("model", model).maybeSingle();
    target = def.data?.version;
  }
  if (!target || target === cur) return new Response(null, { status: 204 });

  const rel = await sb.from("firmware_releases")
    .select("version,path,md5").eq("model", model).eq("version", target).maybeSingle();
  if (!rel.data) return new Response(null, { status: 204 });

  const signed = await sb.storage.from("firmware").createSignedUrl(rel.data.path, 1800); // 30 min
  if (signed.error) return new Response(null, { status: 500 });

  return Response.json({ update: true, version: rel.data.version, url: signed.data.signedUrl, md5: rel.data.md5 });
});
```
Set the function's env: `OTA_TOKEN` — this holds the **fleet token** (baked read-only
at `/etc/bpa/fleet_token` on devices; no OTA secret lives in the device config) — plus
the standard `SUPABASE_URL` / `SERVICE_ROLE_KEY`. Note: the Deno env var keeps the name
`OTA_TOKEN` to match the deployed function; its *value* is the fleet token.

## 3. Publishing an update (your workflow)

1. Build the `recovery.zip` (the builder I provide prints its md5 and the required
   `n7v9_p1-<md5>.zip` name — for OTA the filename doesn't matter, only the md5).
2. Upload it to storage: `firmware/n7v9_p1/<version>/update.zip`.
3. Insert the release row:
   ```sql
   insert into firmware_releases(model,version,path,md5)
   values ('n7v9_p1','9.23.1','n7v9_p1/9.23.1/update.zip','<md5>');
   ```
4. Point devices at it:
   - **All devices:** `insert into firmware_default(model,version) values('n7v9_p1','9.23.1') on conflict (model) do update set version=excluded.version;`
   - **One device:** `insert into device_targets(sn,target_version) values('SV-8396H26031043','9.23.1') on conflict (sn) do update set target_version=excluded.target_version;`
5. Each device picks it up within one `OTA_INTERVAL`, verifies md5, flashes, reboots.

## 4. Security notes
- The **fleet token** is the shared pre-claim secret, baked read-only at `/etc/bpa/fleet_token`
  (no OTA secret is stored in the device config). For a payment/door fleet this is only the
  bootstrap credential: each unit then self-claims a **per-device token** (TOFU claim flow, see
  FIRMWARE_CLAIM_CONTRACT.md) and uses that as its OTA/enroll bearer, so one leaked unit can't
  impersonate others. Rotate the fleet token on compromise.
- Serve the zip via **short-lived signed URLs** (above) so firmware isn't publicly downloadable.
- Defense in depth is already on the device side: webflash checks the manifest md5, and
  **recovery independently re-verifies** the zip's filename-md5, each image's md5, and partition
  sizes before writing — a corrupted or tampered zip fails safe (no flash).
- Keep the local-upload `TOKEN` set (or blank to disable browser upload) and consider firewalling
  port 8090 at your LAN edge; this kernel has no iptables, so the device can't self-firewall it.
