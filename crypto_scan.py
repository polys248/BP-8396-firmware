import os, re, sys

# indicators of cryptographic verification / secure boot
PATS = {
    "rsa":        rb"rsa[ _-]?(public|verify|sign|2048|1024|4096)",
    "sha":        rb"sha-?(1|256|512)",
    "ecdsa/ec":   rb"ecdsa|secp256|ed25519|curve25519",
    "signature":  rb"signature|verify[ _-]?sign|sig[ _-]?verify",
    "secureboot": rb"secure[ _-]?boot|verified[ _-]?boot|chain[ _-]?of[ _-]?trust|dm-verity|fit[ _-]?verify",
    "cert/pem":   rb"-----BEGIN|certificate|x509",
    "efuse":      rb"efuse|otp[ _-]?key|rotpk|root[ _-]?key",
    "mbedtls":    rb"mbedtls|wolfssl|openssl|libcrypto|tomcrypt",
}

def scan(path):
    try:
        d = open(path, "rb").read()
    except Exception:
        return
    hits = {}
    for name, pat in PATS.items():
        m = re.search(pat, d, re.IGNORECASE)
        if m:
            s = re.sub(rb"[^\x20-\x7e]", b".", d[m.start():m.start()+40]).decode()
            hits[name] = (m.start(), s)
    if hits:
        print(f"\n== {os.path.basename(path)} ({len(d):,})")
        for n, (o, s) in hits.items():
            print(f"   {n:<11} @0x{o:x}: {s!r}")

for root in sys.argv[1:]:
    if os.path.isfile(root):
        scan(root)
    else:
        for dp, _, fns in os.walk(root):
            for fn in fns:
                scan(os.path.join(dp, fn))
