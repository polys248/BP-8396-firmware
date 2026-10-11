#!/usr/bin/env python3
"""
md5_vectors.py — canonical MD5 reference for BettaPay enrollment sync.

The device hashes the DECODED bytes (never the base64 text, never a data: URL):
  - Photo:       MD5 over the raw image file bytes (JPEG/PNG).
  - FaceFeature: MD5 over the raw template bytes the base64 decodes to.

Case: the stock web UI sends PhotoMD5 as LOWERCASE hex (CryptoJS default). The
device normalizes an incoming FaceFeatureMD5 to UPPERCASE before comparing, so
its case is effectively don't-care from the sender's side. The authoritative
stored form is whatever `People/GetDetail` reports for a device-enrolled person
— capture it with replay_test.py `vectors` and match that. This script gives the
server a reference implementation + worked vectors to unit-test against.

Pure stdlib; no pip. Usage:
  python3 md5_vectors.py selftest
  python3 md5_vectors.py file  <path-to-image>        # hash raw file bytes
  python3 md5_vectors.py b64    <base64-string|-@file> # decode, then hash
"""
import base64
import hashlib
import sys


def md5_of_bytes(data: bytes):
    h = hashlib.md5(data).hexdigest()   # lowercase hex
    return h, h.upper()


def md5_of_base64(b64_text: str):
    # Hash what the base64 DECODES to — this is the device's definition.
    raw = base64.b64decode(b64_text, validate=False)
    return md5_of_bytes(raw)


def _emit(label: str, lower: str, upper: str):
    print(f"{label}")
    print(f"  lower (stock-UI PhotoMD5 form): {lower}")
    print(f"  UPPER (device FaceFeatureMD5 form): {upper}")


def selftest():
    # Known, independently verifiable vectors so the server can diff against
    # its own implementation before touching a device.
    cases = [
        ("empty string", b""),
        ("ASCII 'abc'", b"abc"),
        ("ASCII 'BettaPay'", b"BettaPay"),
        # base64 of the 4 bytes DE AD BE EF -> hash the 4 raw bytes, not the text
        ("base64 '3q2+7w==' -> bytes DEADBEEF", base64.b64decode("3q2+7w==")),
    ]
    for label, data in cases:
        lo, up = md5_of_bytes(data)
        _emit(label, lo, up)
    print("\nReference expectations (verify with any md5 tool):")
    print("  md5('')     = d41d8cd98f00b204e9800998ecf8427e")
    print("  md5('abc')  = 900150983cd24fb0d6963f7d28e17f72")
    print("Rule: for a base64 field, decode first, then md5 the bytes.")


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd = argv[1]
    if cmd == "selftest":
        selftest()
        return 0
    if cmd == "file" and len(argv) == 3:
        with open(argv[2], "rb") as f:
            lo, up = md5_of_bytes(f.read())
        _emit(f"file {argv[2]}", lo, up)
        return 0
    if cmd == "b64" and len(argv) == 3:
        arg = argv[2]
        if arg.startswith("-@"):
            with open(arg[2:], "r") as f:
                arg = f.read().strip()
        lo, up = md5_of_base64(arg)
        _emit("base64 input (hashed as decoded bytes)", lo, up)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
