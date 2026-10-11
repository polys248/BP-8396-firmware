#!/usr/bin/env python3
"""Minimal OTA server + protocol logger for the A3-8396 (LomboTech N7).

Runs on a machine the DEVICE can reach over the LAN (e.g. CORNERCOMP2). Stdlib
only - works on any Python 3. Two jobs:
  1. Log every request the device makes (method, full path, query, headers) so we
     can see how it formats the update check (SN / version / model params).
  2. Serve a manifest JSON (editable file, no code change to iterate) and the
     firmware pkg with HTTP Range/resume support.

Probing is SAFE: get_upgrade_version just GETs + parses JSON; an invalid or
"not newer" manifest => device does nothing. A flash only happens once the
manifest is valid AND advertises a version newer than the device's current one,
pointing at the pkg below.

usage:
  python3 ota_server.py --pkg slim_923.pkg [--port 8080] [--manifest manifest.json]

The pkg is served at:   /fw/<pkgname-with--MD5>.pkg
Any other path returns the manifest (and is logged), so we discover the real
check path from the first request.
"""
import argparse, hashlib, http.server, json, os, socketserver, sys, time, datetime

def md5_file(p):
    h = hashlib.md5()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_req(self):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        line = f"\n[{ts}] {self.command} {self.path} from {self.client_address[0]}"
        hdrs = "".join(f"\n    {k}: {v}" for k, v in self.headers.items())
        entry = line + hdrs + "\n"
        sys.stdout.write(entry); sys.stdout.flush()
        with open(self.server.logpath, "a", encoding="utf-8") as f:
            f.write(entry)

    def do_HEAD(self): self._serve(head=True)
    def do_GET(self):  self._serve(head=False)

    def _serve(self, head):
        self.log_req()
        path = self.path.split("?", 1)[0]
        if path == self.server.pkg_url:
            return self._serve_pkg(head)
        # anything else: treat as the update-check -> return the manifest
        body = self.server.manifest_bytes
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _serve_pkg(self, head):
        size = os.path.getsize(self.server.pkg_path)
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        if rng and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            if a: start = int(a)
            if b: end = int(b)
            end = min(end, size - 1)
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        length = end - start + 1
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        if head:
            return
        with open(self.server.pkg_path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(1 << 20, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def log_message(self, *a):  # silence default stderr logging
        pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--manifest", default=None, help="JSON file to serve on the check path")
    args = ap.parse_args()

    pkg_path = os.path.abspath(args.pkg)
    md5 = md5_file(pkg_path)
    base = os.path.splitext(os.path.basename(pkg_path))[0]
    # OTA download path extracts the md5 from the filename after the last '-'
    pkg_name = f"{base}-{md5.upper()}.pkg"
    pkg_url = "/fw/" + pkg_name

    if args.manifest and os.path.exists(args.manifest):
        manifest_bytes = open(args.manifest, "rb").read()
    else:
        # placeholder; refine from the device's parse log after first contact
        manifest_bytes = json.dumps({"_note": "placeholder manifest - awaiting device request format"}).encode()

    class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True
    srv = Server(("0.0.0.0", args.port), Handler)
    srv.pkg_path = pkg_path
    srv.pkg_url = pkg_url
    srv.manifest_bytes = manifest_bytes
    srv.logpath = os.path.join(os.path.dirname(pkg_path) or ".", "ota_requests.log")

    print("=" * 64)
    print(f"OTA server on 0.0.0.0:{args.port}")
    print(f"  pkg      : {pkg_path} ({os.path.getsize(pkg_path):,} bytes)")
    print(f"  pkg MD5  : {md5.upper()}")
    print(f"  pkg URL  : http://<THIS-HOST>:{args.port}{pkg_url}")
    print(f"  manifest : {args.manifest or '(placeholder)'} -> served on any other path")
    print(f"  log file : {srv.logpath}")
    print("Set the device's ota_url to  http://<THIS-HOST-LAN-IP>:%d/  then trigger a check." % args.port)
    print("=" * 64)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")

if __name__ == "__main__":
    main()
