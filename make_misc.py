import struct, base64, sys

def bcb(select):
    b = bytearray(0x40)
    struct.pack_into("<I", b, 0x00, 0x20545055)   # magic "UPT "
    struct.pack_into("<I", b, 0x04, 0)            # board_flag
    struct.pack_into("<I", b, 0x08, 0x12345678)   # check_code seed
    struct.pack_into("<I", b, 0x24, select)       # select
    # check_sum = sum of the sixteen u32 LE words (with seed in place)
    s = sum(struct.unpack_from("<16I", b, 0)) & 0xFFFFFFFF
    struct.pack_into("<I", b, 0x08, s)            # store checksum
    return bytes(b), s

for sel in (1, 2):
    b, s = bcb(sel)
    print(f"select={sel}  checksum=0x{s:08x}")
    print("  hex   :", b.hex())
    print("  base64:", base64.b64encode(b).decode())

# write the trigger (select=2) to a file
b2, _ = bcb(2)
open(sys.argv[1], "wb").write(b2)
print(f"\nwrote {sys.argv[1]} (select=2 trigger, {len(b2)} bytes)")
print("device resting misc was: 55505420 00000000 cea68832 ... [0x24]=01  (select=1, csum 0x3288a6ce)")
