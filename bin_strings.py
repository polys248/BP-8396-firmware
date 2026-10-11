import sys, re
raw = open(sys.argv[1], "rb").read()
pats = [p.encode() for p in sys.argv[2:]] or [b"/data", b".pkg", b".zip"]
ss = re.findall(rb"[ -~]{4,}", raw)
seen = set()
for s in ss:
    for p in pats:
        if p in s:
            d = s.decode("latin1", "replace")
            if d not in seen:
                seen.add(d); print(d)
            break
