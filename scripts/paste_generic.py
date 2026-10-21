# -*- coding: utf-8 -*-
"""通用透视贴画：python paste_generic.py <场景图> <画作图> <输出> "x1,y1 x2,y2 x3,y3 x4,y4" """
import sys
import numpy as np
from PIL import Image, ImageEnhance


def find_coeffs(target_quad, src_w, src_h):
    src = [(0, 0), (src_w, 0), (src_w, src_h), (0, src_h)]
    matrix = []
    for (x, y), (u, v) in zip(target_quad, src):
        matrix.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        matrix.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    A = np.matrix(matrix, dtype=float)
    B = np.array(src).reshape(8)
    res = np.dot(np.linalg.inv(A.T * A) * A.T, B)
    return np.array(res).reshape(8)


def main():
    scene_path, paint_path, out_path, quad_str = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    quad = [tuple(int(v) for v in p.split(",")) for p in quad_str.split()]

    scene = Image.open(scene_path).convert("RGB")
    paint = Image.open(paint_path).convert("RGB")
    W, H = scene.size

    top = ((quad[1][0] - quad[0][0]) ** 2 + (quad[1][1] - quad[0][1]) ** 2) ** 0.5
    left = ((quad[3][0] - quad[0][0]) ** 2 + (quad[3][1] - quad[0][1]) ** 2) ** 0.5
    ratio = top / left

    pw, ph = paint.size
    if pw / ph > ratio:
        nw = int(ph * ratio)
        x0 = (pw - nw) // 2
        paint = paint.crop((x0, 0, x0 + nw, ph))
    else:
        nh = int(pw / ratio)
        y0 = (ph - nh) // 2
        paint = paint.crop((0, y0, pw, y0 + nh))

    paint = ImageEnhance.Brightness(paint).enhance(1.06)
    paint = ImageEnhance.Contrast(paint).enhance(0.94)
    paint = ImageEnhance.Color(paint).enhance(0.92)

    pw, ph = paint.size
    coeffs = tuple(float(v) for v in find_coeffs(quad, pw, ph))
    warped = paint.transform((W, H), Image.PERSPECTIVE, coeffs, Image.BICUBIC)
    mask = Image.new("L", (pw, ph), 255).transform((W, H), Image.PERSPECTIVE, coeffs, Image.BILINEAR)

    m = np.array(mask)
    ys, xs = np.nonzero(m > 128)
    print(f"目标 {top:.0f}x{left:.0f} 比例{ratio:.2f} | 掩膜 x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}]")

    out = scene.copy()
    out.paste(warped, (0, 0), mask)
    out.save(out_path, quality=95)
    print("已输出:", out_path)


if __name__ == "__main__":
    main()
