#!/usr/bin/env python3
"""
replay_test.py — single-unit template-replay + MD5-capture kit for the A3-8396.

Drives the device's own web API (the same ingestion path AddPeople uses:
People::FromJson -> PeopleOperate::Save -> face_feat). With one unit it proves
the template round-trips through export->import intact and that a replayed
FaceFeature yields a working recognition, and it captures the device's canonical
PhotoMD5 / FaceFeatureMD5 so the server can match them exactly.

What it does NOT cover (needs a 2nd unit / live backend):
  - cross-hardware portability (enroll on A, recognize on B)
  - the incremental MD5-SKIP decision, which lives in the AddPeople docking path,
    not in the People/New web upsert. Validate that during server integration.

Pure stdlib (urllib, hashlib, base64, json). No pip.

Examples:
  python3 replay_test.py --base-url https://192.168.1.50 --password admin123 list
  python3 replay_test.py --base-url https://192.168.1.50 --password admin123 vectors 1001
  python3 replay_test.py --base-url https://192.168.1.50 --password admin123 export 1001 person.json
  python3 replay_test.py --base-url https://192.168.1.50 --password admin123 replay 1001
    # -> exports person 1001, re-imports the SAME FaceFeature under a fresh UserID,
    #    then stand in front of the unit and confirm the new id recognizes.
"""
import argparse
import base64
import hashlib
import json
import os
import ssl
import sys
import urllib.request
import uuid

TIMEOUT = 20


def _ctx(insecure):
    if insecure:
        c = ssl.create_default_context()
        c.check_hostname = False
        c.verify_mode = ssl.CERT_NONE
        return c
    return None


def _post(base_url, path, body_bytes, content_type, token, insecure):
    req = urllib.request.Request(base_url.rstrip("/") + path, data=body_bytes, method="POST")
    req.add_header("Content-Type", content_type)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    ctx = _ctx(insecure) if base_url.lower().startswith("https") else None
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def post_json(base_url, path, obj, token, insecure):
    return _post(base_url, path, json.dumps(obj).encode(), "application/json; charset=utf-8",
                 token, insecure)


def post_multipart(base_url, path, fields, files, token, insecure):
    # fields: {name: str}; files: {name: (filename, bytes, mime)}
    boundary = "----bpaReplay" + uuid.uuid4().hex
    out = bytearray()
    for name, val in fields.items():
        out += f"--{boundary}\r\n".encode()
        out += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        out += str(val).encode() + b"\r\n"
    for name, (fname, data, mime) in files.items():
        out += f"--{boundary}\r\n".encode()
        out += (f'Content-Disposition: form-data; name="{name}"; filename="{fname}"\r\n'
                f"Content-Type: {mime}\r\n\r\n").encode()
        out += data + b"\r\n"
    out += f"--{boundary}--\r\n".encode()
    return _post(base_url, path, bytes(out),
                 "multipart/form-data; boundary=" + boundary, token, insecure)


def login(base_url, password, insecure):
    salt = uuid.uuid4().hex.upper()
    cipher = hashlib.md5((salt + password + salt).encode()).hexdigest().upper()
    res = post_json(base_url, "/api/User/Login", {"password": cipher, "Hash": salt}, None, insecure)
    if not res.get("result", False):
        raise SystemExit(f"login failed: {res.get('error') or res}")
    token = res["content"]["token"]
    if not token:
        raise SystemExit("login returned empty token")
    return token


def get_detail(base_url, token, userid, insecure):
    res = post_json(base_url, "/api/People/GetDetail", {"UserID": str(userid)}, token, insecure)
    if not res.get("result", False):
        raise SystemExit(f"GetDetail({userid}) failed: {res.get('error') or res}")
    return res["content"]


def search(base_url, token, insecure):
    # The stock table posts paging params; empty keyword returns the roster.
    body = {"Page": 1, "Limit": 50, "Keyword": ""}
    res = post_json(base_url, "/api/People/Search", body, token, insecure)
    return res.get("content", res)


def get_new_id(base_url, token, insecure):
    res = post_json(base_url, "/api/People/GetNewID", {}, token, insecure)
    if res.get("result", False) and isinstance(res.get("content"), dict):
        return str(res["content"].get("UserID") or res["content"].get("NewID") or "")
    return ""


def _show_md5(label, value):
    if value in (None, ""):
        print(f"  {label}: <absent in GetDetail>")
        return
    case = "UPPER" if value == value.upper() else ("lower" if value == value.lower() else "mixed")
    print(f"  {label}: {value}   [{case}, len={len(value)}]")


def cmd_vectors(base_url, token, args, insecure):
    """Capture the device's CANONICAL stored MD5s for a device-enrolled person."""
    d = get_detail(base_url, token, args.userid, insecure)
    print(f"Person {args.userid} ({d.get('Name','?')}):")
    _show_md5("PhotoMD5     (device-stored)", d.get("PhotoMD5"))
    _show_md5("FaceFeatureMD5 (device-stored)", d.get("FaceFeatureMD5"))
    face = d.get("FaceFeature") or ""
    if face:
        raw = base64.b64decode(face, validate=False)
        h = hashlib.md5(raw).hexdigest()
        print(f"  FaceFeature: {len(face)} b64 chars -> {len(raw)} raw bytes")
        print(f"  MD5(decoded FaceFeature bytes): {h}  (UPPER {h.upper()})")
        print("  -> compare this to the device-stored FaceFeatureMD5 above to pin the exact form.")
    photo = d.get("Photo")
    print(f"  Photo field: {photo!r}  PhotoLen={d.get('PhotoLen')}")
    print("\nHand the server the device-stored values above as the golden vectors.")


def cmd_export(base_url, token, args, insecure):
    d = get_detail(base_url, token, args.userid, insecure)
    with open(args.outfile, "w") as f:
        json.dump(d, f, indent=2)
    print(f"exported person {args.userid} -> {args.outfile} "
          f"(FaceFeature {len(d.get('FaceFeature') or '')} chars, "
          f"{len(d.get('Fingerprints') or [])} fp, {len(d.get('Palmveins') or [])} palm)")


def cmd_replay(base_url, token, args, insecure):
    src = get_detail(base_url, token, args.src_userid, insecure)
    if not (src.get("FaceFeature")):
        raise SystemExit(f"person {args.src_userid} has no FaceFeature to replay")
    new_id = args.new_userid or get_new_id(base_url, token, insecure) or (str(args.src_userid) + "9")
    post = {
        "UserID": str(new_id),
        "Name": (src.get("Name") or "Replay") + "_replay",
        "Code": src.get("Code", ""),
        "Department": src.get("Department", ""),
        "CardNum": src.get("CardNum", "0") or "0",
        "Password": "",
        "AccessType": src.get("AccessType", 0),
        "Timegroup": src.get("Timegroup", 0),
        "ExpirationDate": src.get("ExpirationDate", 0),
        "Elevators": "",
        "Holidays": "",
        "FaceFeature": src.get("FaceFeature", ""),
        "Fingerprints": src.get("Fingerprints", []),
        "Palmveins": src.get("Palmveins", []),
        "Photo": "",
        "PhotoLen": 0,
        "PhotoMD5": "",
    }
    res = post_multipart(base_url, "/api/People/New", {"PeopleJson": json.dumps(post)}, {},
                         token, insecure)
    print(f"People/New(new UserID {new_id}) -> {res}")
    if res.get("result", False):
        back = get_detail(base_url, token, new_id, insecure)
        ok = (back.get("FaceFeature") or "") == post["FaceFeature"]
        print(f"round-trip FaceFeature match: {ok}  "
              f"(stored {len(back.get('FaceFeature') or '')} chars)")
        print(f"\nNOW: stand in front of the unit and confirm it recognizes "
              f"UserID {new_id} as the same face. That is the recognition proof.")


def cmd_list(base_url, token, args, insecure):
    data = search(base_url, token, insecure)
    rows = data.get("data") if isinstance(data, dict) else data
    rows = rows or []
    print(f"{len(rows)} people (showing up to 50):")
    for p in rows[:50]:
        print(f"  UserID={p.get('UserID')}  Name={p.get('Name')}  "
              f"Dept={p.get('Department')}  Card={p.get('CardNum')}")


def main(argv):
    ap = argparse.ArgumentParser(description="A3-8396 single-unit replay + MD5 capture kit")
    ap.add_argument("--base-url", required=True, help="e.g. https://192.168.1.50 or http://192.168.1.50")
    ap.add_argument("--password", required=True, help="device admin password (plaintext; salted client-side)")
    ap.add_argument("--insecure", action="store_true", default=True,
                    help="skip TLS verify for the device self-signed cert (default on)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    v = sub.add_parser("vectors"); v.add_argument("userid")
    e = sub.add_parser("export"); e.add_argument("userid"); e.add_argument("outfile")
    r = sub.add_parser("replay"); r.add_argument("src_userid"); r.add_argument("new_userid", nargs="?")
    args = ap.parse_args(argv[1:])

    token = login(args.base_url, args.password, args.insecure)
    print("login OK\n")
    {"list": cmd_list, "vectors": cmd_vectors, "export": cmd_export,
     "replay": cmd_replay}[args.cmd](args.base_url, token, args, args.insecure)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
