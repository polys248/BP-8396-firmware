import re, struct, sys

d = open(sys.argv[1], "rb").read()
print(f"size={len(d)} (0x{len(d):x})")
print("first 64 bytes:")
for o in range(0, 64, 16):
    row = d[o:o+16]
    hexs = " ".join(f"{b:02x}" for b in row)
    txt = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
    print(f"  {o:04x}  {hexs}  {txt}")

# ARM reset vector table = up to 8 words, each either a branch (cond 0xEA / 0xE59FF... ldr pc)
print("\nfirst 8 words (LE) -> ARM decode guess:")
for i in range(8):
    if (i+1)*4 > len(d): break
    w, = struct.unpack_from("<I", d, i*4)
    kind = ""
    if (w >> 24) == 0xEA:
        off = w & 0xFFFFFF
        if off & 0x800000: off -= 0x1000000
        tgt = (i*4 + 8) + off*4
        kind = f"B   -> 0x{tgt:x}"
    elif (w & 0xFFFFF000) == 0xE59FF000:
        kind = f"LDR pc,[pc,#{w & 0xFFF}]"
    print(f"  [{i}] 0x{w:08x}  {kind}")

# printable string runs that look like build/version/base info
print("\nnotable strings:")
for m in re.finditer(rb"[\x20-\x7e]{5,}", d):
    s = m.group().decode()
    if re.search(r"(?i)boot|ver|build|0x[0-9a-f]{6,}|lombo|ddr|load|sram|u-?boot|spl|@", s):
        print(f"  @0x{m.start():x}: {s[:80]}")
