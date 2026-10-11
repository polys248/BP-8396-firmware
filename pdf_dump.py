import sys, io
from pypdf import PdfReader
r = PdfReader(sys.argv[1])
n = len(r.pages)
out = io.open(sys.argv[2], "w", encoding="utf-8")
out.write(f"pages {n}\n")
for i in range(n):
    t = (r.pages[i].extract_text() or "").strip()
    out.write(f"\n==== page {i+1} ====\n")
    out.write(t[:2000] + "\n")
out.close()
print("done", n)
