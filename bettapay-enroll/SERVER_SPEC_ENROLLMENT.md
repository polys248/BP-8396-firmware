# BettaPay org-enrollment backend — implementation guide (server team)

> ## ⚠ REVISION — aligned with BettaPay's multi-tenant model (2026-10-11)
> Server-team review settled the architecture. **Do not create `org` / `org_user` tables.**
> Reuse the existing entities; only the biometric data + sync state are new:
> - **Tenant = org.** Each scanner already belongs to one tenant via
>   `attendance_readers.tenant_id`. Resolve tenant from the device's serial; scope every
>   query to it (RLS + function filter).
> - **Employee = person.** `employees` is tenant-scoped and already carries code, names,
>   department, photo, worksite. BettaPay **already pushes employees to the scanner** via the
>   attendance protocol's `add_people` command, **with `UserID = employee uuid`** — so each
>   device already knows every person by that id. Identity is NOT part of this sync.
> - **Genuinely new:** encrypted **biometric templates keyed by `(tenant_id, employee_id)`**,
>   **per-device cursors**, and the **photo bucket**. That is all `enroll-push`/`enroll-pull`
>   touch. Hang the biometric rows off the employee record (not a parallel roster) so that
>   **employee termination purges templates everywhere** and **tenant offboarding shreds the
>   tenant key**.
> - **Auth:** reuse `authenticateDevice` (device tokens stored as **sha256**, so there's no
>   plaintext column — don't look up by raw token); resolve tenant from `attendance_readers`;
>   a reader whose status ≠ active → `401`.
> - **Keys:** **per-tenant subkey** derived from the master from day one (tenant can be
>   cryptographically shredded on offboarding).
> - **§11 settled:** `user_key` = **employee uuid**, `Code` = employee code (both from
>   BettaPay; no device-minted keys). Access-control = **option (a)** (identity+biometrics+
>   expiration only; device applies a default group). **PINs not synced in v1.** Add two
>   requirements: the feature is **gated by the tenant's attendance add-on**, and a
>   **template purge runs on employee termination/deletion**.
> - Backend supports both template and photo paths, so the **portability test does not block
>   the build**.
>
> ### Device-agent (`bpenroll`) consequences of the above
> - **Biometric-only sync.** The agent does **not** create persons or sync identity — the
>   employee already exists on the device (attendance `add_people`, `UserID = employee uuid`).
>   The agent only **attaches/updates the biometric** on that existing person, keyed by
>   `UserID = employee uuid = user_key`.
> - **Push** when a biometric is enrolled/changed locally: `{employee_uuid, features[], photo}`.
> - **Pull** the tenant's biometrics; for each, find the local person by `UserID` and set its
>   face/finger/palm feature. If the employee isn't on the device yet (attendance hasn't pushed
>   them), **skip and retry next pull** (don't create). Tombstone / termination → remove the
>   local biometric.
> - **Biometric-update path — VERIFIED (2026-10-11), and it's better than expected:**
>   The device's **person record already stores the biometrics as first-class columns** —
>   the people-table upsert is `INSERT ... (userid, name, cardid, password, fingerprint_1,
>   fingerprint_2, fingerprint_3, department, authority, palm_record_id_right,
>   palm_record_id_left, face_feat, face_points, face_norm, …) ON CONFLICT(userid) DO UPDATE
>   SET … face_feat=excluded.face_feat, …`. And the **attendance docking command that already
>   pushes employees — `AddPeople` (`HTTPClient_HTTPv2::DownloadAddPeople`) — writes to that
>   same upsert, including the biometric fields.** So:
>   - **IMPORT (backend → device) should ride the existing `AddPeople` command, not a new agent.**
>     BettaPay already pushes each employee via `AddPeople` with `UserID = employee uuid`; once
>     it has the template, it just populates `face_feat` (+ `face_points`, `face_norm`, the
>     fingerprint/palm fields) in that same command. aio upserts it and the recogniser picks it
>     up. No admin JWT, no local HTTP call, no person-creation race. **Please confirm your
>     `AddPeople` JSON schema exposes the face-feature field** (the device clearly supports it;
>     you may just not be populating it yet) — if so, import needs *zero* new device code.
>   - **EXPORT (device → backend, after a local capture)** is the only genuinely new device job:
>     `bpenroll` reads the just-enrolled person's `face_feat`/`face_points`/`face_norm` (+ finger/
>     palm) from the people DB **directly (root, no JWT)**, keyed by `userid = employee uuid`, and
>     POSTs to `enroll-push`.
>   - A face template is the **triple `face_feat` + `face_points` + `face_norm`** (not a single
>     blob), plus `fingerprint_1..3` and the palm refs — sync all parts together.
>   - The local web `POST /api/People/New` (multipart `PeopleJson` + optional `Photo` file, with
>     `FaceFeature`/`Fingerprints[]`/`Palmveins[]`) is a working upsert too, **but it needs the
>     admin JWT**, so it's a fallback, not the primary path.
> - **DB + protocol — now confirmed (2026-10-11):**
>   - **People DB:** `/data/user.db`, table **`user_data_info`** — columns `id` (autoinc),
>     `userid`, `name`, `cardid`, `password`, `fingerprint_1..3`, `department`, `authority`,
>     `palm_record_id_right/left`, `face_feat`, `face_points`, `face_norm`, `timestamp`,
>     `opening_time_period`, `valid_times`, `YearOfMonth`, `ShiftID`. aio reads it
>     **incrementally by `id`** (`… WHERE id > ? ORDER BY id ASC LIMIT ?`), so a cursor export
>     is natural. Key = `userid` (= employee uuid). Records log is `user_record_info`.
>   - **`AddPeople` schema — fully decoded (2026-10-11, `People::FromJson` @0020f778 +
>     `PeopleFeatureCode::FromJson` @0020e604 + `…ProcessCore`).** The docking parser consumes
>     `{ "PeopleList": [ {person}, … ] }` (confirmed literal). Each person carries — biometric
>     keys **confirmed by name**, demographics confirmed by position/type:
>     - `UserID` (string **or** number — number is auto-stringified), `Name` (+ ~5 demographic
>       strings: Code/Dept/CardNum/Password/… — `Name` and four others are `SanitizeInput`'d
>       on-device), plus access-control ints (Timegroup/OpenTimes/ExpirationDate/ValidTimes/…).
>     - `Photo` (base64) + `PhotoMD5`.
>     - **`FaceFeature`** (base64) + **`FaceFeatureMD5`**.
>     - **`Fingerprints`** and **`Palmveins`** — each an **array of `{ Num:int, Data:string }`**
>       (`PeopleFeatureCode`).
>     aio unpacks `FaceFeature` into the DB's `face_feat`/`face_points`/`face_norm` internally, so
>     **the portable sync unit is the single `FaceFeature` base64** (don't ship the three DB blobs
>     separately). **=> Import is just BettaPay populating `FaceFeature`+`FaceFeatureMD5` in the
>     `AddPeople` it already sends.**
>   - **Incremental sync is MD5-gated — the push MUST include the MD5s.** On a `UserID` that
>     already exists, aio uppercases `FaceFeatureMD5` and `memcmp`s it against the stored value;
>     **equal ⇒ it skips re-pulling that template** (same per-item for fingerprint/palm `Data`).
>     Omit the MD5s and every sync re-downloads every template; include them and sync is
>     incremental for free.
>   - **Biometric blocks are capability-gated.** Each modality is parsed only if the unit
>     advertises it (internal face/FP/palm/card flags). Pushing a palmvein to a face-only device
>     is silently ignored, not an error — so a one-size payload is safe across mixed fleets.
>   - **Sanitize server-side anyway.** The on-device `SanitizeInput` on text fields is a
>     convenience, not a guarantee; these values land directly in local SQLite.
>   - **Export may also be protocol-native.** aio has `PeopleHttpRequestUpload::SavePeopleData`
>     + `people_push_cache_http.json`/`…_mqtt.json` — a **device→backend people upload**. If your
>     reader-gateway's people-upload already includes `FaceFeature`, you receive captured
>     enrollments without new device code; if it strips biometrics, `bpenroll` reads
>     `user_data_info` (face_feat etc., by `userid`) and POSTs `enroll-push`. **Please confirm
>     whether your `SavePeopleData`/people-upload handler carries `FaceFeature`.**
> - **Net:** both directions can ride the existing attendance people-sync once `FaceFeature` is
>   populated — potentially **no new device code at all**, with `bpenroll` only needed if the
>   upload path strips biometrics. The field-by-field decode of the `AddPeople` parser is now
>   complete (above); no further RE is needed to wire the push.
>
> The sections below keep the crypto, edge-function shapes, wire contract, deployment and
> tests — **read them with `org → tenant`, `org_user → employees`, `user_key → employee uuid`,
> and the two new tables hanging off `employees`.**

---

Self-contained build doc for the enrollment-biometric sync backend: schema, auth,
encryption, the two edge functions (`enroll-push`, `enroll-pull`), photo handling,
deployment, security, and tests. Pairs with `ENROLLMENT_SYNC_SPEC.md` (device side) and
reuses the **`device_token`** the claim flow already issues — no new trust bootstrap.

> Status of the one open empirical question: whether we sync **templates** or **photos**
> is decided by `PORTABILITY_TEST.md`. This backend supports **both** (features are opaque
> blobs; photos ride signed URLs), so you can build it now regardless of the result.

---

## 0. How it fits

- A device (`bpenroll` agent) authenticates every call with `Authorization: Bearer <device_token>`
  — the same permanent per-device token from `device-claim`.
- Backend resolves `device_token → (sn, org_id)` and **scopes every query to that org**.
- `enroll-push`: device uploads created/edited/deleted users (+ encrypted templates).
- `enroll-pull`: device fetches org users changed since its cursor and applies them locally.
- Biometric templates are stored **envelope-encrypted**; BettaPay never persists clear biometrics.

Deployment model matches your existing functions (Deno/Supabase Edge, `--no-verify-jwt`,
service-role client, secrets via `supabase secrets set`).

---

## 1. Prerequisites in your current schema

You already have a device-identity table populated by `device-claim` (maps `sn ↔ device_token`)
and `device_remote(sn, token, upload_token, enabled, …)`. This doc assumes a table named
`device` with at least `sn`, `device_token`, `enabled`. **Rename to match your claim schema**
if different — only `resolveDevice()` touches it.

---

## 2. Schema migration

```sql
-- organisations + device membership --------------------------------------------
create table if not exists org (
  id   uuid primary key default gen_random_uuid(),
  name text not null,
  created_at timestamptz default now()
);

-- add org membership to the device identity table (adjust table name to yours)
alter table device add column if not exists org_id uuid references org(id);
create index if not exists device_org_idx on device(org_id);

-- monotonic sync cursor ---------------------------------------------------------
create sequence if not exists enroll_version_seq;
create or replace function next_enroll_version() returns bigint
  language sql volatile as $$ select nextval('enroll_version_seq') $$;

-- canonical org user ------------------------------------------------------------
create table if not exists org_user (
  org_id        uuid not null references org(id),
  user_key      text not null,              -- stable cross-device key (Code, else minted uuid)
  name          text,
  code          text,
  department    text,
  identity_card text,
  card_num      text,
  qrcode        text,
  pin_enc       text,                        -- encrypted PIN, or null if PINs not synced
  access_type   int, timegroup int, open_times int, use_open_times int,
  expiration_date bigint, keep_open int, elevators text, holidays text,
  photo_path    text,                        -- storage object key (private bucket)
  photo_md5     text, photo_len int,
  deleted       boolean not null default false,  -- tombstone
  source_sn     text,                        -- device that last wrote
  version       bigint not null,             -- from next_enroll_version()
  updated_at    timestamptz default now(),
  primary key (org_id, user_key)
);
create index if not exists org_user_sync_idx on org_user(org_id, version);

-- biometric templates, stored ENCRYPTED -----------------------------------------
create table if not exists org_user_feature (
  org_id   uuid not null,
  user_key text not null,
  modality text not null,                    -- 'face' | 'fingerprint' | 'palm'
  num      int  not null default 0,          -- finger/palm index; 0 for face
  data_enc text not null,                    -- AES-256-GCM(iv‖ciphertext) base64 of the template
  version  bigint not null,
  updated_at timestamptz default now(),
  primary key (org_id, user_key, modality, num),
  foreign key (org_id, user_key) references org_user(org_id, user_key) on delete cascade
);
create index if not exists org_feat_sync_idx on org_user_feature(org_id, version);
```

Private storage bucket for photos (one-time): `enroll-photos` (not public).
```sql
insert into storage.buckets (id, name, public) values ('enroll-photos','enroll-photos', false)
  on conflict (id) do nothing;
```

### Row-Level Security (defence in depth)
The functions already scope by `org_id`, but enable RLS so a mistake can't leak across orgs.
Service-role (the functions) bypasses RLS; add policies only if you also expose these tables
to anon/auth keys. Minimum: keep anon/auth **without** select on these tables; access only
through the edge functions.

---

## 3. Secrets / config

```bash
supabase secrets set ENROLL_ENC_KEY=<base64 of 32 random bytes>   # AES-256-GCM master key
# SUPABASE_URL + SERVICE_ROLE_KEY are injected into functions automatically.
```
Generate the key: `openssl rand -base64 32`. **Store it in a secret manager; losing it makes
all stored templates unrecoverable; leaking it defeats the encryption.** For stronger
isolation, derive a per-org subkey (HKDF of master + org_id) — noted in §8.

---

## 4. Shared helpers (`_shared/enroll.ts`)

```ts
import { createClient } from "jsr:@supabase/supabase-js@2";

export const sb = createClient(
  Deno.env.get("SUPABASE_URL")!, Deno.env.get("SERVICE_ROLE_KEY")!,
  { auth: { persistSession: false } },
);

// ---- base64 (chunked; templates can be a few KB) ----
export function toB64(b: Uint8Array): string {
  let s = ""; const C = 0x8000;
  for (let i = 0; i < b.length; i += C) s += String.fromCharCode(...b.subarray(i, i + C));
  return btoa(s);
}
export function fromB64(s: string): Uint8Array {
  const bin = atob(s); const o = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) o[i] = bin.charCodeAt(i);
  return o;
}

// ---- AES-256-GCM envelope encryption of template blobs ----
let KEY: CryptoKey | null = null;
async function key(): Promise<CryptoKey> {
  if (KEY) return KEY;
  KEY = await crypto.subtle.importKey("raw", fromB64(Deno.env.get("ENROLL_ENC_KEY")!),
    "AES-GCM", false, ["encrypt", "decrypt"]);
  return KEY;
}
export async function enc(plain: string): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = new Uint8Array(await crypto.subtle.encrypt({ name: "AES-GCM", iv }, await key(),
    new TextEncoder().encode(plain)));
  const out = new Uint8Array(iv.length + ct.length); out.set(iv, 0); out.set(ct, iv.length);
  return toB64(out);
}
export async function dec(stored: string): Promise<string> {
  const buf = fromB64(stored); const iv = buf.slice(0, 12); const ct = buf.slice(12);
  const pt = new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv }, await key(), ct));
  return new TextDecoder().decode(pt);
}

// ---- auth: device_token -> (sn, org_id) ----
export async function resolveDevice(req: Request): Promise<{ sn: string; org_id: string } | null> {
  const m = (req.headers.get("authorization") || "").match(/^Bearer\s+(.+)$/i);
  if (!m) return null;
  const { data } = await sb.from("device")           // <-- your claim/device table
    .select("sn, org_id, enabled").eq("device_token", m[1].trim()).maybeSingle();
  if (!data || data.enabled === false || !data.org_id) return null;
  return { sn: data.sn, org_id: data.org_id };
}

export function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
```

---

## 5. Edge function `enroll-push`

Device → backend. Upserts changed users + encrypted templates; may hand back a signed PUT URL
for any user whose photo md5 changed so the device can upload the image out-of-band.

```ts
// supabase/functions/enroll-push/index.ts
import { sb, resolveDevice, enc, json } from "../_shared/enroll.ts";

const MAX_CHANGES = 200;

Deno.serve(async (req) => {
  if (req.method !== "POST") return json({ error: "method" }, 405);
  const dev = await resolveDevice(req);
  if (!dev) return json({ error: "unauthorized" }, 401);

  let body: any;
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }
  const changes = Array.isArray(body?.changes) ? body.changes : [];
  if (changes.length === 0) return json({ ok: true, cursor: null, photo_uploads: [] });
  if (changes.length > MAX_CHANGES) return json({ error: "too many changes" }, 413);

  const { data: verRow, error: verErr } = await sb.rpc("next_enroll_version");
  if (verErr) return json({ error: "version" }, 500);
  const version = Number(verRow);

  const photoUploads: { user_key: string; url: string; path: string }[] = [];

  for (const c of changes) {
    const user_key = String(c.user_key ?? "").trim();
    if (!user_key) continue;

    if (c.op === "delete") {
      await sb.from("org_user").update({ deleted: true, version, source_sn: dev.sn, updated_at: new Date().toISOString() })
        .eq("org_id", dev.org_id).eq("user_key", user_key);
      continue;
    }

    // upsert metadata
    const photo_md5 = c.photo_md5 ?? null;
    const row: Record<string, unknown> = {
      org_id: dev.org_id, user_key,
      name: c.name ?? null, code: c.code ?? null, department: c.department ?? null,
      identity_card: c.identity_card ?? null, card_num: c.card_num ?? null, qrcode: c.qrcode ?? null,
      pin_enc: c.pin != null ? await enc(String(c.pin)) : null,
      access_type: c.access_type ?? null, timegroup: c.timegroup ?? null,
      open_times: c.open_times ?? null, use_open_times: c.use_open_times ?? null,
      expiration_date: c.expiration_date ?? null, keep_open: c.keep_open ?? null,
      elevators: c.elevators ?? null, holidays: c.holidays ?? null,
      photo_md5, photo_len: c.photo_len ?? null,
      deleted: false, source_sn: dev.sn, version, updated_at: new Date().toISOString(),
    };
    // photo path: stable per user; only (re)upload when md5 changed
    const existing = await sb.from("org_user").select("photo_md5, photo_path")
      .eq("org_id", dev.org_id).eq("user_key", user_key).maybeSingle();
    let photo_path = existing.data?.photo_path ?? null;
    if (photo_md5 && existing.data?.photo_md5 !== photo_md5) {
      photo_path = `${dev.org_id}/${user_key}.jpg`;
      const signed = await sb.storage.from("enroll-photos").createSignedUploadUrl(photo_path);
      if (!signed.error) photoUploads.push({ user_key, url: signed.data.signedUrl, path: photo_path });
    }
    row.photo_path = photo_path;
    await sb.from("org_user").upsert(row, { onConflict: "org_id,user_key" });

    // replace templates for this user (encrypt each)
    if (Array.isArray(c.features)) {
      await sb.from("org_user_feature").delete().eq("org_id", dev.org_id).eq("user_key", user_key);
      for (const f of c.features) {
        if (!f?.data) continue;
        await sb.from("org_user_feature").insert({
          org_id: dev.org_id, user_key,
          modality: String(f.modality || "face"), num: Number(f.num ?? 0),
          data_enc: await enc(String(f.data)), version,
        });
      }
    }
  }

  return json({ ok: true, cursor: version, photo_uploads: photoUploads });
});
```

The device then `PUT`s each photo to its `url` (image/jpeg), out-of-band from the JSON.

---

## 6. Edge function `enroll-pull`

Device → backend. Returns org users changed since the device's cursor, templates **decrypted**
(the device needs the clear template to enroll locally), photos as signed GET URLs, tombstones
included so deletes propagate.

```ts
// supabase/functions/enroll-pull/index.ts
import { sb, resolveDevice, dec, json } from "../_shared/enroll.ts";

const PAGE = 200;

Deno.serve(async (req) => {
  const dev = await resolveDevice(req);
  if (!dev) return json({ error: "unauthorized" }, 401);

  const u = new URL(req.url);
  const since = Number(u.searchParams.get("since") ?? "0") || 0;
  const limit = Math.min(Number(u.searchParams.get("limit") ?? PAGE) || PAGE, PAGE);

  const { data: users, error } = await sb.from("org_user")
    .select("user_key,name,code,department,identity_card,card_num,qrcode,pin_enc,access_type,timegroup,open_times,use_open_times,expiration_date,keep_open,elevators,holidays,photo_path,photo_md5,photo_len,deleted,version")
    .eq("org_id", dev.org_id).gt("version", since)
    .order("version", { ascending: true }).limit(limit);
  if (error) return json({ error: "query" }, 500);

  let cursor = since;
  const out: any[] = [];
  for (const r of users ?? []) {
    cursor = Math.max(cursor, Number(r.version));
    if (r.deleted) { out.push({ user_key: r.user_key, deleted: true }); continue; }

    const feats = await sb.from("org_user_feature")
      .select("modality,num,data_enc").eq("org_id", dev.org_id).eq("user_key", r.user_key);
    const features = [];
    for (const f of feats.data ?? []) features.push({ modality: f.modality, num: f.num, data: await dec(f.data_enc) });

    let photo_url = null;
    if (r.photo_path) {
      const s = await sb.storage.from("enroll-photos").createSignedUrl(r.photo_path, 1800);
      if (!s.error) photo_url = s.data.signedUrl;
    }

    out.push({
      user_key: r.user_key, deleted: false,
      name: r.name, code: r.code, department: r.department, identity_card: r.identity_card,
      card_num: r.card_num, qrcode: r.qrcode,
      pin: r.pin_enc ? await dec(r.pin_enc) : null,
      access_type: r.access_type, timegroup: r.timegroup, open_times: r.open_times,
      use_open_times: r.use_open_times, expiration_date: r.expiration_date, keep_open: r.keep_open,
      elevators: r.elevators, holidays: r.holidays,
      photo_md5: r.photo_md5, photo_len: r.photo_len, photo_url,
      features,
    });
  }

  return json({ cursor, more: (users?.length ?? 0) === limit, users: out });
});
```

---

## 7. Wire contract (what `bpenroll` sends/expects)

**Push** `POST {API_BASE}/enroll-push`  ·  `Authorization: Bearer <device_token>`
```jsonc
{ "changes": [
  { "op":"upsert", "user_key":"EMP001", "code":"EMP001", "name":"Ada",
    "department":"Ops", "identity_card":"...", "card_num":"0", "qrcode":"",
    "access_type":0, "timegroup":0, "open_times":65535, "use_open_times":0,
    "expiration_date":4102415940, "keep_open":0, "elevators":"", "holidays":"",
    "pin": null,
    "photo_md5":"<hex>", "photo_len":12345,
    "features":[ {"modality":"face","num":0,"data":"<base64 template>"} ],
    "client_updated_at": 1699999999 },
  { "op":"delete", "user_key":"EMP002", "client_updated_at": 1699999999 }
] }
```
→ `{ "ok":true, "cursor":<version>, "photo_uploads":[ {"user_key":"EMP001","url":"<signed PUT>","path":"..."} ] }`
Device PUTs each changed photo to its signed `url` (`Content-Type: image/jpeg`).

**Pull** `GET {API_BASE}/enroll-pull?since=<cursor>&limit=200`  ·  `Authorization: Bearer <device_token>`
→
```jsonc
{ "cursor": <max version in page>, "more": true,
  "users":[
    { "user_key":"EMP001", "deleted":false, "code":"EMP001", "name":"Ada", …meta…,
      "photo_url":"<signed GET|null>",
      "features":[ {"modality":"face","num":0,"data":"<base64 template>"} ] },
    { "user_key":"EMP002", "deleted":true }
  ] }
```
Device keeps `cursor` in `/data`, loops while `more` is true, applies each user via the
local People API (`People/New` with `FaceFeature`, else download `photo_url` +
`EnrollUserMediaData`), and maps `user_key → local UserID`.

---

## 8. Security & compliance (NDPR / biometric data)

- **Templates encrypted at rest** (AES-256-GCM). The DB holds only ciphertext; a dump without
  `ENROLL_ENC_KEY` exposes no biometrics. Decrypted only in the function response to an
  authenticated org device.
- **Per-org key (recommended hardening):** derive `k_org = HKDF(ENROLL_ENC_KEY, org_id)` and
  encrypt/decrypt with that, so a single org's data can be cryptographically shredded by
  rotating its subkey. Drop-in change in `enc/dec` (take `org_id`).
- **Strict org scoping:** every query filters by the resolved `org_id`; enable RLS and keep
  anon/auth keys off these tables (access only via functions).
- **Photos:** private bucket, short-lived signed URLs only. Optionally encrypt photo bytes
  app-side too (same envelope) before upload for parity with templates.
- **PINs:** prefer **not** syncing door PINs; if required, `pin_enc` only, never clear in DB.
- **Deletion / data-subject rights:** a delete sets `deleted=true` (propagation), then a purge
  job removes the `org_user_feature` rows, the photo object, and nulls PII after propagation
  confirmed. Keep an audit of `source_sn`/`version`.
- **Transport:** devices call over HTTPS (ttproxy). Rotate `device_token` by disabling the
  device (the claim/enable flow) to cut a unit off from org data.
- **Consent/retention:** out of scope here but required operationally — record enrollment
  consent and a retention policy; the schema supports purge.

---

## 9. Deployment

```bash
supabase functions deploy enroll-push --no-verify-jwt
supabase functions deploy enroll-pull --no-verify-jwt
# (device sends device_token, not a Supabase JWT — same as fw-manifest/remote-enroll)
supabase secrets set ENROLL_ENC_KEY=$(openssl rand -base64 32)
# run the schema migration (section 2) + create the private bucket
```
Endpoints become `https://api.bettapay.ng/functions/v1/enroll-push` and `…/enroll-pull`.

Provision: set each device's `org_id` (`update device set org_id=… where sn=…`). Devices with
no `org_id` get `401` (not yet assigned to an org) — safe default.

---

## 10. Smoke tests (curl)

```bash
API=https://api.bettapay.ng/functions/v1
DT=<a device_token whose device.org_id is set>

# push one user with a (fake) face template
curl -s -X POST "$API/enroll-push" -H "Authorization: Bearer $DT" -H "Content-Type: application/json" \
 -d '{"changes":[{"op":"upsert","user_key":"EMP001","code":"EMP001","name":"Ada",
      "card_num":"0","access_type":0,"timegroup":0,"open_times":65535,"use_open_times":0,
      "expiration_date":4102415940,"keep_open":0,"elevators":"","holidays":"",
      "features":[{"modality":"face","num":0,"data":"QUJDREVGRz0="}]}]}'
# -> {"ok":true,"cursor":1,"photo_uploads":[]}

# pull from a second device in the same org (cursor 0 = everything)
curl -s "$API/enroll-pull?since=0&limit=50" -H "Authorization: Bearer <DT_device2>"
# -> {"cursor":1,"more":false,"users":[{"user_key":"EMP001",...,"features":[{"modality":"face","num":0,"data":"QUJDREVGRz0="}]}]}
```
Verify the pulled `features[].data` **equals** what was pushed (round-trips through encrypt/decrypt),
and that a device whose `org_id` is unset gets `401`.

---

## 11. Decisions we need from you

1. Confirm the device-identity table name/columns for `resolveDevice()` (`device.device_token`,
   `device.org_id`, `device.enabled`).
2. `user_key`: use `Code` when the org uses employee codes, else the device mints a UUID — OK?
3. Access-control fields (`timegroup`/`elevators`/`holidays`) are device-local ids. v1: carry
   them but have the device apply an org-default group, per `ENROLLMENT_SYNC_SPEC.md §6`. Agree?
4. Sync PINs or not.
5. Per-org subkey (recommended) vs single master key for v1.

Once (1)–(5) are set and `PORTABILITY_TEST.md` says template-vs-photo, this backend and the
`bpenroll` device agent can be built in parallel.
