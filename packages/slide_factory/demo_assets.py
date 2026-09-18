"""Generate placeholder figures for the demo decks (pure Pillow).

Rough evocations of typical quantum-device figures — swap in real figures
for real talks. `build(dir)` (re)generates them and returns {name: path}.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GREY = (70, 70, 70)


def _font(size):
    for cand in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/System/Library/Fonts/Helvetica.ttc", "arial.ttf"):
        try:
            return ImageFont.truetype(cand, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _rounded(d, xy, r=26, **kw):
    d.rounded_rectangle(xy, radius=r, **kw)


def pipeline_grid(path, w=1180, h=1180):
    """Grid of shuttling loops with qubit dots ('looped pipeline')."""
    im = Image.new("RGBA", (w, h), "white")
    d = ImageDraw.Draw(im)
    cell, pad = 290, 100
    # translucent check regions behind the loops
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(ov)
    for (i, j), col in {(0, 0): (200, 226, 200), (1, 1): (238, 200, 192),
                        (2, 0): (238, 200, 192), (0, 2): (200, 226, 200),
                        (2, 2): (200, 226, 200), (1, 2): (238, 200, 192)}.items():
        x, y = pad + i * (cell + 60), pad + j * (cell + 60)
        od.ellipse([x - 45, y - 45, x + cell + 45, y + cell + 45], fill=col + (150,))
    im.alpha_composite(ov)
    d = ImageDraw.Draw(im)
    dots = [(226, 130, 78), (86, 130, 190), (140, 90, 160), (220, 170, 60)]
    for i in range(3):
        for j in range(3):
            x, y = pad + i * (cell + 60), pad + j * (cell + 60)
            _rounded(d, [x, y, x + cell, y + cell], r=34, outline=GREY, width=10)
            _rounded(d, [x + 55, y + 55, x + cell - 55, y + cell - 55],
                     r=22, outline=GREY, width=6)
            for k, (cx, cy) in enumerate([(x, y), (x + cell, y), (x, y + cell),
                                          (x + cell, y + cell)]):
                d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16],
                          fill=dots[(k + i + j) % 4], outline="white", width=3)
    im.convert("RGB").save(path)


def snakes_grid(path, w=1500, h=1100):
    """Tilted patchwork of dotted device tiles ('snakes on a plane')."""
    im = Image.new("RGBA", (w, h), "white")
    d = ImageDraw.Draw(im)
    size, step = 240, 260
    for row in range(-1, 5):
        for col in range(-1, 7):
            x = col * step + (28 if row % 2 else -18)
            y = row * step + (18 if col % 2 else -12)
            fill = (207, 226, 243) if (row + col) % 2 else (255, 255, 255)
            _rounded(d, [x, y, x + size, y + size], r=30, fill=fill,
                     outline=(120, 120, 120), width=5)
            # dotted inner border (green)
            n = 14
            for k in range(n):
                fx = x + 26 + k * (size - 52) / (n - 1)
                for yy in (y + 24, y + size - 30):
                    d.rectangle([fx, yy, fx + 7, yy + 7], fill=(90, 150, 80))
            for k in range(3):
                d.rectangle([x + size - 20, y + 60 + k * 26,
                             x + size - 8, y + 78 + k * 26], fill=(90, 150, 80))
    ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(ov).ellipse([w * 0.30, h * 0.30, w * 0.72, h * 0.66],
                               fill=(120, 160, 110, 120))
    im.alpha_composite(ov)
    im.convert("RGB").save(path)


def potential_wells(path, w=1500, h=1000):
    """Travelling double-well potential with localized wavefunctions."""
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    f, fs = _font(40), _font(30)

    def V(x):
        base = 0.10 * math.sin(x / w * 6 * math.pi)
        g1 = -0.62 * math.exp(-((x - 0.34 * w) ** 2) / (2 * (w * 0.045) ** 2))
        g2 = -0.38 * math.exp(-((x - 0.66 * w) ** 2) / (2 * (w * 0.045) ** 2))
        return base + g1 + g2

    pts = [(x, h * 0.42 - V(x) * h * 0.42) for x in range(60, w - 60, 4)]
    # wavefunction blobs in the wells
    for cx, col in ((0.34 * w, (232, 80, 59)), (0.66 * w, (60, 90, 200))):
        for rad, a in ((150, 28), (110, 55), (70, 95), (38, 160)):
            ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            ImageDraw.Draw(ov).ellipse([cx - rad, h * 0.68 - rad * 0.62,
                                        cx + rad, h * 0.68 + rad * 0.62],
                                       fill=col + (a,))
            im.paste(Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB"), (0, 0))
    d = ImageDraw.Draw(im)
    d.line(pts, fill=(40, 40, 40), width=9, joint="curve")
    d.line([60, h * 0.9, w - 60, h * 0.9], fill=GREY, width=5)
    d.polygon([(w - 60, h * 0.9), (w - 95, h * 0.9 - 16), (w - 95, h * 0.9 + 16)], fill=GREY)
    d.text((w - 210, h * 0.92), "x (shuttle)", font=fs, fill=GREY)
    # gate voltage tags
    for cx, col, tag in ((0.34 * w, (232, 80, 59), "V₁"), (0.66 * w, (60, 90, 200), "V₂")):
        _rounded(d, [cx - 60, 40, cx + 60, 120], r=18, fill=col)
        d.text((cx, 80), tag, font=f, fill="white", anchor="mm")
        d.line([cx, 120, cx, h * 0.30], fill=col, width=5)
    # dashed transfer arrow
    x0, x1, y = 0.40 * w, 0.60 * w, h * 0.62
    for xx in range(int(x0), int(x1), 36):
        d.line([xx, y, xx + 18, y], fill=(40, 40, 40), width=7)
    d.polygon([(x1 + 14, y), (x1 - 16, y - 15), (x1 - 16, y + 15)], fill=(40, 40, 40))
    im.save(path)


def device_stack(path, w=1500, h=820):
    """Si/SiO2 gate-stack cross-section with a shuttled electron."""
    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im)
    f, fs = _font(44), _font(34)
    d.text((w / 2, 100), "Gate-defined shuttling channel", font=f,
           fill=(60, 60, 60), anchor="mm")
    d.rectangle([80, 480, w - 80, 740], fill=(226, 226, 230), outline=GREY, width=6)
    d.text((w / 2, 620), "Si substrate", font=f, fill=(70, 70, 70), anchor="mm")
    d.rectangle([80, 360, w - 80, 480], fill=(199, 223, 241), outline=GREY, width=6)
    d.text((320, 420), "SiO₂", font=f, fill=(50, 80, 110), anchor="mm")
    n = 7
    for k in range(n):
        x = 130 + k * (w - 260 - 130) / (n - 1)
        col = (232, 80, 59) if k == 3 else (90, 96, 108)
        _rounded(d, [x, 210, x + 130, 360], r=20, fill=col)
        d.text((x + 65, 285), f"G{k + 1}", font=fs, fill="white", anchor="mm")
    # channel + electron
    yc = 495
    for xx in range(110, w - 110, 40):
        d.line([xx, yc, xx + 20, yc], fill=(150, 60, 40), width=6)
    ex = 130 + 3 * (w - 260 - 130) / (n - 1) + 65
    d.ellipse([ex - 26, yc - 26, ex + 26, yc + 26], fill=(240, 150, 40),
              outline=(120, 70, 0), width=5)
    d.text((ex + 50, yc - 55), "e⁻", font=f, fill=(120, 70, 0))
    im.save(path)


BUILDERS = {"pipeline": pipeline_grid, "snakes": snakes_grid,
            "wells": potential_wells, "device": device_stack}


def build(directory) -> dict[str, Path]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, fn in BUILDERS.items():
        p = directory / f"{name}.png"
        fn(p)
        out[name] = p
    return out


if __name__ == "__main__":
    for name, p in build(Path(__file__).parent / "out" / "demo" / "assets").items():
        print(name, "->", p)
