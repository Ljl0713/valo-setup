# -*- coding: utf-8 -*-
"""生成应用图标 valo.ico —— 纯 Python 手写 ICO（32bpp 位图，无第三方依赖）
图案：红色底 + 白色 4:3 画幅框，一眼看出是「画幅比例」主题。
"""
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "valo.ico")

RED = (0x55, 0x46, 0xFF, 255)      # BGRA: #ff4655
WHITE = (0xFF, 0xFF, 0xFF, 255)
SIZES = [16, 32, 48, 64, 128, 256]


def render(size):
    """返回 BGRA 像素数组（自上而下），以及是否为透明像素"""
    px = bytearray(size * size * 4)
    # 4:3 画幅框：内缩 size/8，按 4:3 比例
    bw = int(size * 0.68)
    bh = int(bw * 3 / 4)
    x0 = (size - bw) // 2
    y0 = (size - bh) // 2
    lw = max(1, size // 16)
    for y in range(size):
        for x in range(size):
            i = (y * size + x) * 4
            col = RED
            if x0 <= x < x0 + bw and y0 <= y < y0 + bh:
                edge = min(x - x0, x0 + bw - 1 - x, y - y0, y0 + bh - 1 - y)
                if edge < lw:
                    col = WHITE
            px[i:i + 4] = bytes(col)
    return px


def bmp_for_ico(px, size):
    """ICO 内部位图：BITMAPINFOHEADER + BGRA 自下而上 + AND 掩码"""
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0,
                         size * size * 4, 0, 0, 0, 0)
    rows = bytearray()
    for y in range(size - 1, -1, -1):
        rows += px[y * size * 4:(y + 1) * size * 4]
    mask_row = ((size + 31) // 32) * 4
    mask = bytes(mask_row * size)
    return header + bytes(rows) + mask


def main():
    images = [(s, bmp_for_ico(render(s), s)) for s in SIZES]
    dir_hdr = struct.pack("<HHH", 0, 1, len(images))
    offset = 6 + 16 * len(images)
    entries, blobs = b"", b""
    for s, data in images:
        entries += struct.pack("<BBBBHHII", 0 if s == 256 else s, 0 if s == 256 else s,
                               0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    with open(OUT, "wb") as f:
        f.write(dir_hdr + entries + blobs)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")

    # 自校验：解析回来检查目录项数量与偏移
    raw = open(OUT, "rb").read()
    r, t, c = struct.unpack("<HHH", raw[:6])
    print("check: type=%d count=%d first_size=%d last_size=%d" % (
        t, c, struct.unpack("<BBBBHHII", raw[6:22])[0],
        struct.unpack("<BBBBHHII", raw[6 + 16 * (c - 1):6 + 16 * c])[0]))
    assert t == 1 and c == len(SIZES)
    print("OK")


if __name__ == "__main__":
    main()
