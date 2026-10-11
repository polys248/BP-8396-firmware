# Answers to your three questions (all resolved from the firmware)

Great news on both confirmations — with export carrying `FaceFeature` and your `AddPeople`
replaying it, the feature rides the existing protocol end-to-end and **no device code ships**.
Agreed on dropping `enroll-pull`, the `org`/`org_user` sections and the plaintext-token lookup.

## 1. MD5 definition — hash the DECODED bytes, hex, UPPERCASE

The device hashes the **raw/decoded bytes, not the base64 text and not a data URL**, and stores the
digest as **uppercase hex**.

- **Photo:** `CreateFileMD5_Hex` runs over the image **file** after it's written (base64 decoded
  via `base2file`, or downloaded from the URL). So: MD5 of the actual JPEG/PNG binary.
- **FaceFeature:** `CreateBytesMD5_Hex(buf, len)` → `CreateBytesMD5` over the **raw template
  bytes** → `BytesToHex`. The DB stores the template as a raw blob; `CreatePeopleByDB` hashes that
  blob directly (6 call sites). So: MD5 of the bytes the base64 decodes to.
- **Case:** `…ProcessCore` `ToUpper`s the incoming `FaceFeatureMD5` before `memcmp` against a
  value it recomputes locally. Device-to-device replay only matches if both sides are the same
  case, which forces the canonical form to **uppercase**. Send uppercase hex.

So when you originate/alter a photo or template in the back-office: **base64-decode first, MD5 the
bytes, hex-encode, uppercase.** Hashing the base64 string will make the device think every record
changed and re-pull every template.

## 2. Photo as URL — yes, the receiver downloads it

`AddDownloadPhoto` calls `HTTPUtil::IsHttpUrl(Photo)`:
- **URL** → it builds an `HTTPClient_DownloadTask` and the download manager fetches it.
- **not a URL** → it treats the string as base64 and writes the file with `base2file`.

So your avatar-URL approach works as-is — **no need to inline base64.** Same logic applies to
`FaceFeature` (`AddDownloadFace` → `IsHttpUrl`: URL is downloaded; a non-URL value is kept and
persisted as the inline template). Either form is accepted for both fields.

Two caveats for the URL path:
- The device fetches the URL itself, so it must be reachable **from the terminal's network** and
  live long enough for the (possibly queued/retried) download — a short-lived signed URL can
  expire before the device drains its queue.
- `PhotoMD5` is still matched against the downloaded bytes, so compute it over the image the URL
  returns (per §1).

## 3. UserID-only pushes — the device has no record for that id; do NOT fetch

`CreatePushPeopleRequestBody` attaches the **full** `People::ToJson` (plus the photo part) whenever
a `People` object is present. `PushPeople_Handler` builds that object via `FindByUserID` per queued
event — so **the device always includes the record when it has one.** A UserID-only push therefore
means `FindByUserID` returned nothing: the device holds **no record** for that id (a local delete /
tombstone for the queued event).

- It is **not** a "fetch it from me" prompt — there is nothing on the device to fetch.
- Every push carries an **operation-code** field (the numeric form field; e.g. the full-resync
  loop sends code `4`). **Key off that code.** For the body-less case, reconcile as "device has no
  record for this id" (treat per your delete semantics); don't call back.

**Critical retry contract (please implement):** the device considers a push successful **only if you
return HTTP 200 with a JSON body whose `code == 1`.** On anything else it leaves the event queued
and **re-sends the whole queue indefinitely** (it checkpoints with `SaveSettingToFile` every ~10
successes). So ack each push with `200 {"code":1}`, including the body-less ones, or you'll get an
unbounded resend loop.

## On your build order

All of it looks right. Two notes tied to the above:
- The **MD5-gated skip** (`…ProcessCore` uppercases `FaceFeatureMD5` and `memcmp`s before
  re-pulling) is what makes "replay the complete record to every reader" cheap — unchanged
  templates are never re-downloaded. Keep the MD5s populated on every replay.
- "Protect stored biometrics from a detail-less push" matches the device's own behavior: on an
  existing `UserID` it only overwrites a biometric when the incoming MD5 differs, and a push
  without the biometric field leaves the stored one untouched. Mirroring that server-side is
  correct.

On UserID: understood — employee uuid for BettaPay-origin people, terminal id for device-origin
people, unique per tenant and reused across readers. Dedup by `UserID` holds fleet-wide, which is
exactly what the device's `FindByUserID` keys on. PIN + ID number in v1 is fine; they're just more
`People` string fields to the device.

Portability test still stands on our side too — the record carries both template and photo, so it
doesn't block anything.
