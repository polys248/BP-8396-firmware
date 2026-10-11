# BettaPay org-wide enrollment sync — design spec

Goal: enroll a person at **one** station and have them recognised on **all** devices
in the same organisation. Built on the fleet infra already in place (per-device
`device_token`, the authenticated tunnel, OTA).

---

## 1. The enrollment record (what we sync)

A person is created on a device via `POST /api/People/New` with this payload (field
names verified from the device web UI, `page/people/edit.html`):

### Identity
| Field | Notes |
|------|------|
| `UserID` | **device-local**, assigned by the device on create (`result.content.NewUserID`). NOT a cross-device key. |
| `Code` | user/employee code — the natural **cross-device key** (if the org uses it) |
| `Name` | |
| `Department` | free text |
| `IdentityCard` | national ID etc. |
| `CardNum` | RFID card number ("0" if none) |
| `QRCode` | optional |
| `Password` | door PIN (optional, ≥4 digits) |

### Access control (⚠ device-local references — see §6)
`AccessType`, `Timegroup` (int), `OpenTimes` (65535 = unlimited), `UseOpenTimes` (0/1),
`ExpirationDate` (unix; default `4102415940`), `KeepOpen` (0/1), `Elevators` (csv),
`Holidays` (csv).

### Biometrics (the portable part)
| Field | Shape |
|------|------|
| `FaceFeature` | **base64 string** — the face template |
| `Fingerprints` | array of `{ num, data }` (base64 per finger) |
| `Palmveins` | array of `{ num, data }` (base64 per palm) |

### Photo
`Photo` (filename), `PhotoLen` (bytes), `PhotoMD5` (hex). Image bytes uploaded alongside
(the web UI posts the file with the record). Also re-derivable per device from the photo
via `POST /api/People/EnrollUserMediaData` (`{UserID, type:"Face"}`) which makes the
device extract its own template from stored media.

### Export (device → us)
`POST /api/People/Search {PageIndex,PageSize}` → list (`content.DataList`, `content.TotalCount`);
`POST /api/People/GetDetail {UserID}` → full record incl. `FaceFeature`/`Fingerprints`/`Palmveins`
and photo refs. So a device can export any enrollment as JSON.

### Import (us → device)
`POST /api/People/New` with the record above (inject `FaceFeature` directly) — fast path.
Fallback if templates aren't portable (see test): push the **photo**, then
`EnrollUserMediaData` so the target device extracts its own template.

---

## 2. Two sync strategies (decided by the portability test)

- **Template sync (preferred):** ship the base64 `FaceFeature` and inject via `People/New`.
  Fast, no camera, works headless. Requires templates to be portable across units
  (same model + facial engine 6.01 → expected; confirm with `PORTABILITY_TEST.md`).
- **Photo sync (fallback):** ship the enrollment **photo**; each device re-extracts its own
  template via `EnrollUserMediaData`. Always works (same algorithm re-runs locally), but
  needs a usable frontal photo per user and more device CPU.

The feature works either way; the test only decides which path (or a hybrid: template
with photo as backup).

---

## 3. BettaPay data model (Supabase)

```sql
-- organisations and device membership
create table org ( id uuid primary key default gen_random_uuid(), name text not null );
alter table device_remote add column org_id uuid references org(id);   -- group devices by org

-- canonical org user (one row per person per org)
create table org_user (
  org_id        uuid references org(id),
  user_key      text,                 -- stable cross-device key (Code, else a minted uuid)
  name          text,
  code          text,
  department    text,
  identity_card text,
  card_num      text,
  qrcode        text,
  pin_enc       text,                 -- encrypted PIN if synced (or omit PINs from sync)
  access_type   int, timegroup int, open_times int, use_open_times int,
  expiration_date bigint, keep_open int, elevators text, holidays text,
  photo_path    text,                 -- storage key (encrypted bucket)
  photo_md5     text, photo_len int,
  version       bigint not null,      -- monotonic; bumped on every change (sync cursor)
  updated_at    timestamptz default now(),
  source_sn     text,                 -- which device last wrote
  deleted       boolean default false,-- tombstone (propagates removals)
  primary key (org_id, user_key)
);

-- biometric templates, stored ENCRYPTED (BettaPay never holds clear biometrics)
create table org_user_feature (
  org_id    uuid, user_key text,
  modality  text,                     -- 'face' | 'fingerprint' | 'palm'
  num       int default 0,            -- finger/palm index; 0 for face
  data_enc  text not null,            -- envelope-encrypted base64 template
  version   bigint not null,
  primary key (org_id, user_key, modality, num)
);
create index on org_user (org_id, version);
create index on org_user_feature (org_id, version);
```

Photos: encrypted storage bucket, access via short-lived signed URLs, org-scoped.

---

## 4. Sync protocol (device ↔ BettaPay)

Auth: `Authorization: Bearer <device_token>` (same token as OTA/enroll). The backend maps
`device_token → sn → org_id`, and **every query is org-scoped** (RLS), so a device only ever
sees its own org's users.

### Push (device → BettaPay), after a local enroll/edit/delete
```
POST {API_BASE}/enroll-push
{ "changes": [
    { "op":"upsert", "user_key":"...", "name":"...", "code":"...", ...meta...,
      "features":[ {"modality":"face","num":0,"data":"<base64>"} , ... ],
      "photo_md5":"...", "client_updated_at": 1699999999 },
    { "op":"delete", "user_key":"...", "client_updated_at": 1699999999 }
] }
```
Backend: encrypt `features[].data` → `data_enc`, upsert `org_user`/`org_user_feature`,
bump `version = nextval`. Photos uploaded via a returned signed-URL PUT (keeps the JSON small).

### Pull (device → BettaPay), periodically / on reconnect
```
GET {API_BASE}/enroll-pull?since=<cursor>&limit=200
-> { "cursor": <new>, "users":[
      { "user_key":"...", "deleted":false, ...meta...,
        "features":[ {"modality":"face","num":0,"data":"<base64>"} ],   // decrypted for the device
        "photo_url":"<signed>" }, ... ] }
```
Device applies each: new (by `code`/`user_key`) → `People/New` (inject `FaceFeature`); existing
→ `People/Edit`; `deleted` → `People/Delete`. Device keeps a `user_key → local UserID` map and
the last `cursor` in `/data`.

**Instant fan-out (optional):** when a push lands, BettaPay signals other org devices over the
**existing bpagent tunnel** to pull now, instead of waiting for the poll.

Conflict: last-writer-wins by `client_updated_at`; `source_sn` recorded for audit.

---

## 5. Device-side agent (`bpenroll`, new — sibling of bpagent)

- **Export loop:** detect local changes (`People/Search` watermark by an updated field, or a
  post-enroll hook) → build change batch → `enroll-push`.
- **Import loop:** `enroll-pull?since=cursor` → apply via local People API → advance cursor.
- Offline-safe: queue outbound in `/data`, reconcile on reconnect. Memory-bounded like bpagent.
- Auth via `device_token`; HTTPS via ttproxy. Ships in the rootfs + OTA, same pipeline as the rest.

---

## 6. Open questions / gotchas to decide

1. **Stable key.** Is `Code` always present + unique per org? If yes → `user_key = Code`.
   If not → mint a UUID at first enroll, store it on the origin device, carry it in sync.
2. **Access-control references are device-local.** `Timegroup`, `Elevators`, `Holidays` are
   *numbers/ids that point at config on that device*. `Timegroup=2` only means the same thing
   on device B if B has the same Timegroup 2 configured. v1 options: (a) sync identity +
   biometrics + `ExpirationDate` only, apply an org-default access group on each device; or
   (b) also standardise the access-control config org-wide (bigger). Recommend (a) for v1.
3. **Capacity.** Each device has a face capacity (`BigFaceCapacity`); the org roster must fit.
   Backend should expose org user count; agent should warn/stop near the device limit.
4. **PINs/passwords.** Decide whether door PINs sync at all; if so, store encrypted, never clear.
5. **Compliance (NDPR / biometric data).** Templates + photos + PII centralised. Required:
   envelope-encryption at rest (BettaPay stores opaque blobs), org-scoped access (RLS),
   consent + retention policy, and data-subject deletion (tombstone **and** purge of
   `data_enc`/photo). Transport already TLS via ttproxy.
6. **Dedup / re-enroll.** `EnrollUserMediaDataRepetition` shows the device detects duplicate
   faces — decide whether a cross-device import should hard-replace or skip on duplicate.

---

## 7. Build order

1. **Run `PORTABILITY_TEST.md`** — decides template-sync vs photo-sync. (Gating.)
2. Backend: `org` + `org_user` + `org_user_feature` + storage + `enroll-push`/`enroll-pull`
   (Supabase edge functions, device_token auth, org-scoped RLS, envelope encryption).
3. Firmware: `bpenroll` agent (export/import loops), baked + OTA.
4. Pilot with 2 devices in one org; then fan-out.

Everything here authenticates with the `device_token` we already provision and rides the
HTTPS/tunnel we already have — no new trust bootstrap needed.
