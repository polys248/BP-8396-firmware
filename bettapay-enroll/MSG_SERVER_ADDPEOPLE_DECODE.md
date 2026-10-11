# AddPeople parser — full device-side decode (import path confirmed)

We finished reverse-engineering the device's `AddPeople` receiver. **Import needs no new
device code** — populate the fields below on the `AddPeople` command you already push, and
the terminal ingests biometrics directly. Details and the two confirmation asks are below.

## 1. Wire format

```jsonc
{
  "PeopleList": [            // envelope key confirmed (literal cJSON_GetObjectItem(root,"PeopleList"))
    {
      "UserID":        "…",  // string OR number (number is auto-stringified). = employee uuid. Dedup key.
      "Name":          "…",
      // …demographic/access fields (Code, Department, CardNum, Password, Authority,
      //    Timegroup, OpenTimes, ExpirationDate, ValidTimes, …) — use the same keys
      //    you already send on AddPeople / that /api/People/New accepts.
      "Photo":         "<base64>",
      "PhotoMD5":      "<hex>",
      "FaceFeature":   "<base64>",   // the single portable face template
      "FaceFeatureMD5":"<hex>",      // REQUIRED for incremental sync — see §2
      "Fingerprints":  [ { "Num": 1, "Data": "<base64>" }, … ],
      "Palmveins":     [ { "Num": 1, "Data": "<base64>" }, … ]
    }
  ]
}
```

- `FaceFeature` is **one base64 blob**. The device unpacks it internally into its three DB
  columns (`face_feat` / `face_points` / `face_norm`) — **do not** try to send those three
  separately. One template in, one template out.
- `Fingerprints` / `Palmveins` are arrays of `{ Num, Data }` (device type `PeopleFeatureCode`:
  `Num` = int slot index, `Data` = base64 template).

Evidence: decoded `People::FromJson` (@0x0020f778), `PeopleFeatureCode::FromJson` (@0x0020e604),
and `HTTPClient_HTTPv2::DownloadAddPeopleResponseProcessCore`. `PeopleList`, `FaceFeature`,
`FaceFeatureMD5`, `Photo`, `PhotoMD5`, and the FP/palm array shape are confirmed verbatim;
demographic keys are confirmed by struct position/type (they match `/api/People/New`, which you
already use).

## 2. The one non-obvious must-have: send the MD5s

On a `UserID` that already exists on the device, the receiver **uppercases `FaceFeatureMD5` and
`memcmp`s it against the stored value — if they match, it skips re-downloading that template.**
Same per-item for fingerprint/palm `Data`.

- **Include the MD5s →** sync is incremental for free; unchanged templates are never re-pulled.
- **Omit the MD5s →** every sync re-downloads every template for every person. On a large roster
  this is the difference between a few-KB delta and re-pushing the whole biometric set each run.

So: always set `FaceFeatureMD5` (and the photo/FP/palm MD5s where you have them).

## 3. Capability gating (good news — one payload fits the whole fleet)

Each biometric block is parsed **only if the unit advertises that modality** (internal
face / fingerprint / palm / card flags). Pushing a palmvein to a face-only terminal is **silently
ignored, not an error**. So you can send a uniform payload across mixed hardware without
per-device branching.

## 4. Server-side sanitization

The device runs `SanitizeInput` on `Name` and several text fields, but treat that as a
convenience, not a guarantee — these values land directly in the terminal's local SQLite.
Please sanitize/validate server-side too.

## 5. Two things we need you to confirm

1. **Sender side (import):** does the `AddPeople` your backend emits already populate
   `FaceFeature` + `FaceFeatureMD5`? The device *receiver* is now proven to consume them; we just
   need the *sender* to fill them. If it does, **import is done with no device changes.**
2. **Export side:** does your device→backend people-upload path
   (`PeopleHttpRequestUpload::SavePeopleData` / `people_push_cache_*.json`) carry `FaceFeature`?
   - If **yes**, you receive captured enrollments with no new device code either.
   - If **no (biometrics stripped)**, that's the only case where we ship `bpenroll` — a small
     agent that reads `user_data_info` by `userid` and POSTs `enroll-push`.

Everything else (schema, `enroll-push`/`enroll-pull`, crypto, photo handling, deployment, tests)
is in `SERVER_SPEC_ENROLLMENT.md`.
