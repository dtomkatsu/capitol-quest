#!/usr/bin/env python3
"""Pixel-art sprites for Capitol Quest: the State Capitol landmark,
landmark marker, and water-sparkle animation frames.

Outputs site/assets/sprites/*.png
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "assets" / "sprites"


def hx(s, a=255):
    s = s.lstrip("#")
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16), a)


def put(img, x, y, c):
    if 0 <= y < img.shape[0] and 0 <= x < img.shape[1]:
        img[y, x] = c


def ellipse(img, cx, cy, rx, ry, fill, rim=None):
    for y in range(cy - ry, cy + ry + 1):
        for x in range(cx - rx, cx + rx + 1):
            d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if d <= 1.0:
                put(img, x, y, fill)
    if rim:
        for y in range(cy - ry, cy + ry + 1):
            for x in range(cx - rx, cx + rx + 1):
                d = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
                if 0.82 <= d <= 1.0:
                    put(img, x, y, rim)


def cone(img, cx, base_y, top_y, base_half, top_half, body, lt, dk):
    """Truncated volcano cone (the real chamber roofs are flat-topped)."""
    hgt = base_y - top_y
    for i in range(hgt + 1):
        y = top_y + i
        half = top_half + (base_half - top_half) * i // max(1, hgt)
        img[y, cx - half:cx + half + 1] = body
        img[y, cx - half:cx - half + 2] = lt
        img[y, cx + half - 1:cx + half + 1] = dk
    img[top_y, cx - top_half:cx + top_half + 1] = dk   # open crater rim


def capitol():
    """The Hawaiʻi State Capitol, gentle 3/4 aerial view. Signature reads:
    slender full-height columns rising from the plaza, capitals flaring
    into a cornice that sweeps OUTWARD and UPWARD past the wall plane (the
    'crown'), a flat roof deck behind it with the open-to-the-sky rotunda,
    and the two squat truncated chamber cones barely cresting the roofline.
    Seated on its plaza (the reflecting pool was drawn until 2026-08-21,
    then removed — user's call)."""
    W, H = 112, 86
    img = np.zeros((H, W, 4), np.uint8)

    white = hx("#f5f2e9")
    white_dk = hx("#ddd9cc")
    cornice = hx("#fbf9f2")
    cornice_sh = hx("#c6c2b4")
    shadow = hx("#57524a")
    deep_sh = hx("#454138")
    deck = hx("#cfccbf")
    court = hx("#8e8878")
    cone_c = hx("#a89a82")
    cone_lt = hx("#c0b39c")
    cone_dk = hx("#7c7060")

    # ---- plaza (slightly wider than when the pool ringed it, so the
    # building still sits on a full apron of ground)
    ellipse(img, 56, 69, 50, 11, hx("#d9d5c9"), hx("#a9a598"))

    WALL_L, WALL_R = 14, 99            # wall plane

    # ---- open ground level: deep shade, columns run down to the plaza
    img[54:63, WALL_L:WALL_R] = deep_sh
    img[62, WALL_L:WALL_R] = hx("#8b8578")          # plaza line

    # ---- upper office floors (2-5): recess + horizontal louver ribbons
    img[36:54, WALL_L:WALL_R] = shadow
    for y in range(39, 53, 4):
        img[y, WALL_L + 1:WALL_R - 1] = hx("#6a6458")

    # ---- slender full-height columns (plaza to capitals)
    for cx in range(16, 96, 6):
        img[36:62, cx:cx + 2] = white
        img[36:62, cx + 1:cx + 2] = white_dk        # right shade line

    # ---- capital flare band: each column widens into a scallop
    for cx in range(16, 96, 6):
        img[35, cx - 1:cx + 3] = white
        img[34, cx - 2:cx + 4] = white
    img[33, WALL_L:WALL_R] = cornice_sh

    # ---- the crown: cornice stepping OUTWARD and UPWARD past the walls
    img[32, WALL_L - 1:WALL_R + 1] = white_dk
    img[31, WALL_L - 2:WALL_R + 2] = white_dk
    img[30, WALL_L - 4:WALL_R + 4] = white
    img[29, WALL_L - 6:WALL_R + 6] = white
    img[28, WALL_L - 7:WALL_R + 7] = cornice        # upswept lip, brightest
    # upturned tips
    img[27, WALL_L - 7:WALL_L - 3] = cornice
    img[27, WALL_R + 3:WALL_R + 7] = cornice

    # ---- roof deck behind the crown, rotunda open to the sky
    img[22:28, WALL_L + 2:WALL_R - 2] = deck
    img[22, WALL_L + 2:WALL_R - 2] = hx("#e4e1d4")  # sunlit deck edge
    img[23:28, 36:77] = court                       # open rotunda well
    img[23, 36:77] = hx("#6e6a5c")

    # ---- the two chamber cones: squat, truncated, just cresting the deck
    cone(img, 44, 26, 19, 10, 6, cone_c, cone_lt, cone_dk)   # Senate (ʻEwa)
    cone(img, 69, 26, 19, 10, 6, cone_c, cone_lt, cone_dk)   # House (Diamond Head)

    # ---- modest flag at the ʻEwa corner
    img[8:22, 20:21] = hx("#77726a")
    img[8:10, 21:29] = hx("#f0f0f0")
    img[10:12, 21:29] = hx("#c03b46")
    img[12:14, 21:29] = hx("#2b4f9e")
    img[8:11, 21:24] = hx("#2b4f9e")

    # ---- flanking palms at the plaza edge
    for px, flip in ((7, 1), (105, -1)):
        for i in range(10):
            put(img, px + flip * (i // 4), 64 - i, hx("#8a5a33"))
        tx, ty = px + flip * 2, 53
        for dx, dy in ((-4, 0), (-2, -2), (0, -3), (2, -2), (4, 0),
                       (-5, 2), (5, 2)):
            put(img, tx + dx, ty + dy, hx("#3f8f3f"))
            put(img, tx + dx // 2, ty + dy // 2 - 1, hx("#63b45a"))
    return img


def marker():
    W, H = 16, 20
    img = np.zeros((H, W, 4), np.uint8)
    gold, dark, lite = hx("#f2c14e"), hx("#b07d1e"), hx("#ffe9a8")
    for dy in range(7):
        half = dy if dy < 4 else 6 - dy
        img[2 + dy, 8 - half - 1:8 + half + 1] = gold
    for dy in range(7):
        half = dy if dy < 4 else 6 - dy
        put(img, 8 - half - 1, 2 + dy, dark)
        put(img, 8 + half, 2 + dy, dark)
    put(img, 7, 3, lite)
    put(img, 6, 4, lite)
    img[11:13, 7:9] = gold          # tail dot
    img[14:17, 7:9] = dark          # shadow tick
    return img


def sparkles():
    frames = []
    for f in range(3):
        img = np.zeros((9, 9, 4), np.uint8)
        w = hx("#eaf6ff")
        b = hx("#9fd4f0")
        if f == 0:
            put(img, 4, 4, b)
        elif f == 1:
            for d in (-1, 0, 1):
                put(img, 4 + d, 4, w)
                put(img, 4, 4 + d, w)
        else:
            for d in range(-3, 4):
                put(img, 4 + d, 4, w if abs(d) < 2 else b)
                put(img, 4, 4 + d, w if abs(d) < 2 else b)
            put(img, 3, 3, b)
            put(img, 5, 5, b)
        frames.append(img)
    return frames


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray(capitol(), "RGBA").save(OUT / "capitol.png")
    Image.fromarray(marker(), "RGBA").save(OUT / "marker.png")
    for i, fr in enumerate(sparkles()):
        Image.fromarray(fr, "RGBA").save(OUT / f"sparkle_{i}.png")
    print("wrote", sorted(p.name for p in OUT.glob("*.png")))


if __name__ == "__main__":
    main()
