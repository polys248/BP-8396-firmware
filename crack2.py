import sys, time
from passlib.hash import sha512_crypt

HASH = "$6$0LfwOVw43ndnyYwt$cKKYBcAsIhkk2hJK9i37kXAH/TxUX8XfRyzYlZFJpSSTn.9vX8CGA0f.4VOqB0.CsN/LVe/4kcCVG3NEyvBq2."
wl = sys.argv[1]
words = [w.rstrip("\n") for w in open(wl, encoding="latin1")]
# add simple mangles of a few device terms
extra = []
for b in ["faceds","fulang","n7v9","virgo","lombo","a38396","admin","root"]:
    for s in ["","123","1234","12345","@123","888","2020","2021","2022","2023","!","#1"]:
        extra.append(b+s); extra.append((b+s).capitalize())
words = extra + words

t0 = time.time()
hit = None
for i, w in enumerate(words):
    try:
        if sha512_crypt.verify(w, HASH):
            hit = w; break
    except Exception:
        pass
    if i % 500 == 0 and i:
        r = i/(time.time()-t0)
        open("crack_result.txt","w").write(f"progress {i}/{len(words)} ({r:.0f}/s)\n")

dt = time.time()-t0
msg = (f"FOUND: root password = {hit!r}\n" if hit is not None
       else f"NOT FOUND in {len(words)} candidates ({dt:.0f}s)\n")
open("crack_result.txt","w").write(msg)
print(msg)
