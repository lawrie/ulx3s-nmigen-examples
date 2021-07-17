import sys

with open(sys.argv[2], 'wb') as bmp:
    # BMP Header
    bmp.write(b'BM')

    # file size
    bmp.write(b"\x36\x10\x0E\x00")

    # unused
    bmp.write(b"\x00\x00\x00\x00")

    # offset
    bmp.write(b"\x36\x00\x00\x00")

    # 40-byte header
    bmp.write(b"\x28\x00\x00\x00")

    # width 640
    bmp.write(b"\x80\x02\x00\x00")

    # height 480, top to bottom
    bmp.write(b"\x20\xFE\xFF\xFF")

    # 1 plane
    bmp.write(b"\x01\x00")

    # 24 bits
    bmp.write(b"\x18\x00")

    # No compression
    bmp.write(b"\x00\x00\x00\x00")

    # Size of bitmap
    bmp.write(b"\x00\x01\x0E\x00")

    # print resolution
    bmp.write(b"\x13\x0b\x00\x00")
    bmp.write(b"\x13\x0b\x00\x00")

    # 0 colors
    bmp.write(b"\x00\x00\x00\x00")
    # 0 important colors
    bmp.write(b"\x00\x00\x00\x00")

    with open(sys.argv[1], 'rb') as dmp:
        p = dmp.read(2)
        while p:
            i = int.from_bytes(p,"little")
            r = (i >> 11) << 3
            g = ((i >> 5) & 0x3f) << 2
            b = (i & 0x1f) << 3
            p = dmp.read(2)
            # Duplicate pixel
            for j in range(2):
                bmp.write(b.to_bytes(1, "little"))
                bmp.write(g.to_bytes(1, "little"))
                bmp.write(r.to_bytes(1, "little"))


