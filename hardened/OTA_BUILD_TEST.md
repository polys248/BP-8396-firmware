# A3-8396 OTA backend — build & test (bettapay / Supabase)

Goal: publish a firmware on your backend; the device's `webflash` OTA client pulls
it over HTTPS, verifies, and flashes via recovery. Test the **server in isolation
with curl first** (no device risk), then do **one safe end-to-end run** with a
harmless test firmware, then go live.

--------------------------------------------------------------------------------
## PART A — Build the backend

### A1. Storage
Create a **private** bucket named `firmware`. You'll upload each build to a path
like `n7v9_p1/<version>/update.zip`.

### A2. Tables (SQL editor)
```sql
create table firmware_releases (
  model text not null,
  version text not null,
  path text not null,          -- storage path, e.g. 'n7v9_p1/otatest1/update.zip'
  md5 text not null,           -- lowercase hex md5 of the zip
  created_at timestamptz default now(),
  primary key (model, version)
);
create table firmware_default ( model text primary key, version text not null );
create table device_targets   ( sn text primary key,   target_version text not null );
```
(No RLS policies needed — only the edge function touches these, with the service role.)

### A3. Edge function `fw-manifest`
`supabase/functions/fw-manifest/index.ts`:
```ts
import { createClient } from "jsr:@supabase/supabase-js@2";

const OTA_TOKEN = Deno.env.get("OTA_TOKEN")!;              // env var name; value = the fleet token
const sb = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SERVICE_ROLE_KEY")!);

Deno.serve(async (req) => {
  if (req.headers.get("authorization") !== `Bearer ${OTA_TOKEN}`)
    return new Response("unauthorized", { status: 401 });

  const u = new URL(req.url);
  const sn    = u.searchParams.get("sn")    ?? "";
  const cur   = u.searchParams.get("ver")   ?? "";
  const model = u.searchParams.get("model") ?? "n7v9_p1";

  // target = per-device override, else global default
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
  if (signed.error) return new Response(JSON.stringify({ error: "sign" }), { status: 500 });

  return Response.json({ update: true, version: rel.data.version, url: signed.data.signedUrl, md5: rel.data.md5 });
});
```
Deploy + set the secret (CLI):
```
supabase functions deploy fw-manifest --no-verify-jwt
supabase secrets set OTA_TOKEN=<the-fleet-token>   # env var name stays OTA_TOKEN; value = fleet token
# SUPABASE_URL / SERVICE_ROLE_KEY are provided to functions automatically.
```
`--no-verify-jwt` is required: the device sends the **fleet token** (pre-claim) or its
per-device token (post-claim) as the Bearer, not a Supabase JWT, and the function checks
it itself. Your endpoint URL becomes
`https://api.bettapay.ng/functions/v1/fw-manifest`.

--------------------------------------------------------------------------------
## PART B — TEST 1: server only, with curl (no device, zero risk)

### B1. Publish the harmless test firmware
`ota_test.zip` (I sent it) flips `pkg_ver` to `OTATEST001` — boot-irrelevant.
- md5: `2c8c9f4cc5d391c7f93b0ae35e40d5d4`
Upload it and register it:
```
# upload (dashboard: Storage > firmware > upload to  n7v9_p1/otatest1/update.zip)
# then in SQL:
insert into firmware_releases(model,version,path,md5)
values ('n7v9_p1','otatest1','n7v9_p1/otatest1/update.zip','2c8c9f4cc5d391c7f93b0ae35e40d5d4');
insert into device_targets(sn,target_version)
values ('SV-8396H26031043','otatest1')
on conflict (sn) do update set target_version=excluded.target_version;
```

### B2. Simulate the device's checks
Update available (device on some older `ver`):
```
curl -i "https://api.bettapay.ng/functions/v1/fw-manifest?sn=SV-8396H26031043&ver=none&model=n7v9_p1" \
  -H "Authorization: Bearer <OTA_TOKEN>"
```
Expect `200` + JSON: `{"update":true,"version":"otatest1","url":"https://...signed...","md5":"2c8c9f4cc5d391c7f93b0ae35e40d5d4"}`.

Confirm the signed URL really serves the zip and the md5 matches:
```
curl -s "<the url field from above>" -o /tmp/dl.zip && md5sum /tmp/dl.zip
```
Should print `2c8c9f4cc5d391c7f93b0ae35e40d5d4`.

No update (device already on target) → expect `204`:
```
curl -i "https://api.bettapay.ng/functions/v1/fw-manifest?sn=SV-8396H26031043&ver=otatest1&model=n7v9_p1" \
  -H "Authorization: Bearer <OTA_TOKEN>"
```
Bad token → expect `401`:
```
curl -i "https://api.bettapay.ng/functions/v1/fw-manifest?sn=SV-8396H26031043&ver=none" -H "Authorization: Bearer wrong"
```
When all three behave as above, the server is correct. **No device was touched.**

--------------------------------------------------------------------------------
## PART C — TEST 2: safe end-to-end on the device

Keep `device_targets` pointing the SN at `otatest1` (the harmless firmware).

On the device, set the OTA config and a known starting version, then restart webflash:
```
# /data/webflash/config  -> set these:
#   OTA_URL=https://api.bettapay.ng/functions/v1/fw-manifest
#   OTA_INTERVAL=120          # short, just for the test
#   DEVICE_SN=SV-8396H26031043
# No OTA secret in this file. For the test, drop the fleet token (= the function's
# OTA_TOKEN value) so webflash has a bearer pre-claim:
printf '%s' '<the-fleet-token>' > /data/fleet_token && chmod 600 /data/fleet_token
echo pretest > /data/webflash/version          # make it report an old version
kill $(pidof webflash) 2>/dev/null
/data/webflash/webflash >> /data/webflash/webflash.log 2>&1 &
tail -f /data/webflash/webflash.log
```
Within ~2 min you should see: `ota: enabled ...` then `ota: update offered: otatest1 ...`,
a download, then the device stages + reboots into recovery to flash.

After it boots back:
```
dd if=/dev/mtdblock11 bs=16 count=1 2>/dev/null | od -c      # -> O T A T E S T 0 0 1
cat /data/webflash/version                                   # -> otatest1
```
- `pkg_ver` = `OTATEST001` → **OTA pulled and flashed from your backend, end to end.**
- `version` = `otatest1` → the device now reports the new version, so the next check
  returns `204` (no re-flash loop). That's the designed behavior.

Then put `OTA_INTERVAL` back to `3600` (or your preference) and restart webflash.

--------------------------------------------------------------------------------
## PART D — go live / publish a real update
1. Build a real `recovery.zip` (ask me for the builder) and note its md5.
2. Upload to `n7v9_p1/<version>/update.zip`.
3. `insert into firmware_releases(model,version,path,md5) values('n7v9_p1','<version>','n7v9_p1/<version>/update.zip','<md5>');`
4. Point devices:
   - all: `insert into firmware_default(model,version) values('n7v9_p1','<version>') on conflict (model) do update set version=excluded.version;`
   - one (canary first!): update that SN's `device_targets` row.
5. Each device pulls within one `OTA_INTERVAL`, md5-verifies, flashes. Recovery
   re-verifies filename-md5 + per-image md5 + sizes before writing → fails safe.

### Rollback
Point `firmware_default` / `device_targets` back to a previous known-good `version`;
devices on the bad one will "update" to the older build on their next check.

### Safety
- Keep the fleet token secret. For a fleet it's only the bootstrap credential: each unit
  self-claims a per-device token (TOFU claim flow) that becomes its real OTA/enroll bearer.
- Serve only via the short-lived signed URLs above (never a public bucket).
- Canary one SN via `device_targets` before setting `firmware_default` fleet-wide.
