import sys
p = sys.argv[1]
d = bytearray(open(p, "rb").read())
old = b"http://119.23.124.50:8731//YZ8395H/VerifyData"
repl = b"http://127.0.0.1/disabled"   # inert; same-or-shorter, null-padded

n = 0
i = d.find(old)
if i < 0:
    # not the exact literal — report context around the IP so we can adjust
    j = d.find(b"119.23.124.50")
    if j < 0:
        print("ERROR: neither full URL nor IP found in", p); sys.exit(1)
    ctx = bytes(d[max(0, j-16): j+48])
    print("full URL not found; IP context:", ctx); sys.exit(2)

assert len(repl) <= len(old), "replacement too long"
new = repl + b"\x00" * (len(old) - len(repl))
while i >= 0:
    d[i:i+len(old)] = new
    n += 1
    i = d.find(old, i+len(new))
open(p, "wb").write(d)
print(f"patched {n} occurrence(s): {old.decode()} -> {repl.decode()} (+{len(old)-len(repl)} NUL)")

# sanity: ensure the IP no longer appears as part of that URL
left = d.find(b"119.23.124.50")
print("remaining '119.23.124.50' occurrences after patch:", 0 if left < 0 else d.count(b"119.23.124.50"))
