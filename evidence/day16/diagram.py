from PIL import Image, ImageDraw, ImageFont
# Run from the repository root: python3 evidence/day16/diagram.py
src = "evidence/day14/factory-diagram.png"
im = Image.open(src).convert("RGB")
W, H = im.size
EXT = 320
out = Image.new("RGB", (W, H + EXT), (255, 255, 255))
out.paste(im, (0, 0))
d = ImageDraw.Draw(out)
F = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
R = "/System/Library/Fonts/Supplemental/Arial.ttf"
f_title = ImageFont.truetype(F, 30); f_b = ImageFont.truetype(F, 21); f_r = ImageFont.truetype(R, 18)
# band
top = H + 30
d.rounded_rectangle((12, top, W - 12, H + EXT - 70), 22, fill=(224, 242, 241))
d.text((32, top + 14), "Security scan (Day 16)", font=f_title, fill=(15, 32, 66))
TEAL_F, TEAL_S = (204, 251, 241), (15, 118, 110)
def box(x0, y0, x1, y1, lines, fill, stroke, dash=False, width=3):
    if dash:
        d.rounded_rectangle((x0, y0, x1, y1), 14, fill=fill)
        for (a, b, c, e) in [(x0, y0, x1, y0), (x0, y1, x1, y1), (x0, y0, x0, y1), (x1, y0, x1, y1)]:
            n = int(max(abs(c - a), abs(e - b)) // 14)
            for i in range(0, n, 2):
                t0, t1 = i / n, min((i + 1) / n, 1)
                d.line((a + (c - a) * t0, b + (e - b) * t0, a + (c - a) * t1, b + (e - b) * t1), fill=stroke, width=width)
    else:
        d.rounded_rectangle((x0, y0, x1, y1), 14, fill=fill, outline=stroke, width=width)
    total = sum((f.size + 6) for f, _ in lines) - 6
    y = (y0 + y1) / 2 - total / 2
    for f, t in lines:
        w = d.textlength(t, font=f)
        d.text(((x0 + x1) / 2 - w / 2, y), t, font=f, fill=(15, 23, 42))
        y += f.size + 6
def arrow(x0, y0, x1, y1, color=(15, 32, 66), dash=False):
    if dash:
        n = int(max(abs(x1 - x0), abs(y1 - y0)) // 10)
        for i in range(0, n, 2):
            d.line((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n, x0 + (x1 - x0) * (i + 1) / n, y0 + (y1 - y0) * (i + 1) / n), fill=color, width=3)
    else:
        d.line((x0, y0, x1, y1), fill=color, width=4)
    import math
    a = math.atan2(y1 - y0, x1 - x0); L = 16
    p = [(x1, y1), (x1 - L * math.cos(a - 0.45), y1 - L * math.sin(a - 0.45)), (x1 - L * math.cos(a + 0.45), y1 - L * math.sin(a + 0.45))]
    d.polygon(p, fill=color)
mx = 481  # master centre x in the 1024px image
# arrow from master down into the band
arrow(mx, 2030, mx, top + 82)
d.text((mx + 10, 2060), "copy of master", font=f_r, fill=(15, 32, 66))
# A: the scan we ran
A = (mx - 190, top + 82, mx + 190, top + 212)
box(*A, [(f_b, "Arnica scan (ran once)"), (f_r, "org copy keynes-factory/Project.Keynes"), (f_r, "master @ e8dad5f, scan-only setup"), (f_r, "secrets · SAST · SCA · IaC")], TEAL_F, TEAL_S)
# B: where I inspect findings
B = (mx + 250, top + 82, W - 30, top + 212)
box(*B, [(f_b, "I read findings"), (f_r, "in the Arnica dashboard;"), (f_r, "fix, investigate or dismiss")], (237, 233, 254), (109, 40, 217), width=4)
arrow(A[2], (A[1] + A[3]) / 2, B[0], (B[1] + B[3]) / 2)
# C: planned
C = (30, top + 82, mx - 230, top + 212)
box(*C, [(f_b, "Arnica PR check"), (f_b, "+ notifications"), (f_r, "(planned, per PR)")], (241, 245, 249), (100, 116, 139), dash=True)
# no flow arrow to the planned box
# legend row
ly = H + EXT - 50
d.rounded_rectangle((20, ly, 70, ly + 28), 6, fill=TEAL_F, outline=TEAL_S, width=3)
d.text((82, ly + 2), "Teal: Arnica (added Day 16)", font=f_r, fill=(15, 23, 42))
out.save("evidence/day16/factory-diagram.png")
print(out.size)
