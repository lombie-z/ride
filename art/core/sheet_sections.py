"""The look on top of art/core/render_sections.py's raw stills, about as the site has it (fog to dark green, bloom, a grade), a copy at the scene's pixel
(1/7), the contact sheet with the references beside them, and the road's side elevation and plan: python3 art/core/sheet_sections.py
-> art/renders/sections/{m1..}.png, sheet.png, road-elevation.png, road-plan.png."""
import json
import os
import sys

sys.dont_write_bytecode = True
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import road_sections as R  # noqa: E402

ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
SEC = os.path.join(ROOT, 'art', 'renders', 'sections')
RAW = os.path.join(SEC, 'raw')
FOG_STAIR = np.array([0.05, 0.25, 0.13])
FOG_FLOOD = np.array([0.02, 0.05, 0.035])
ORDER = ['m1', 'm2', 'm3', 'm4', 'm5a', 'm5b', 'm6', 'm7', 'm7b', 'm8a', 'm8b', 'm9stop', 'm9open', 'm9gap', 'm9room']
try:
    F = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 16)
    FB = ImageFont.truetype('/System/Library/Fonts/Menlo.ttc', 22)
except OSError:
    F = FB = ImageFont.load_default()


def post(shot):
    p = os.path.join(RAW, shot + '.png')
    img = np.asarray(Image.open(p).convert('RGB'), float) / 255.0
    f = np.asarray(Image.open(os.path.join(RAW, shot + '-fog.png')).convert('L'), float)[..., None] / 255.0
    col = FOG_FLOOD if shot.startswith(('m8', 'm9')) else FOG_STAIR
    c = img * (1 - f) + col * f
    glow = np.clip(c - 0.6, 0, 1) * 2.2
    im = Image.fromarray((np.clip(glow, 0, 1) * 255).astype(np.uint8))
    g1 = np.asarray(im.filter(ImageFilter.GaussianBlur(5)), float) / 255.0
    g2 = np.asarray(im.filter(ImageFilter.GaussianBlur(24)), float) / 255.0
    c = c + g1 * 0.6 + g2 * 0.75
    return Image.fromarray((np.clip(c, 0, 1) ** 1.05 * 255).astype(np.uint8))


def pix(im, k=7):
    w, h = im.size
    return im.resize((w // k, h // k), Image.NEAREST).resize((w // k * k, h // k * k), Image.NEAREST)


def label(im, text):
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, im.size[0], 26), fill=(0, 0, 0))
    d.text((8, 4), text, fill=(210, 240, 215), font=F)
    return im


def sheet():
    titles = {}
    for n in ('stair', 'flood'):
        p = os.path.join(RAW, n + '-titles.json')
        if os.path.exists(p):
            titles.update(json.load(open(p)))
    W, H = 640, 360
    done = {}
    tiles = []
    for name, t in (('concept-stairwell', 'REFERENCE: stairwell'), ('concept-flooded-tunnel', 'REFERENCE: flooded tunnel')):
        ref = Image.open(os.path.join(ROOT, 'art', 'reference', name + '.webp')).convert('RGB').resize((W, H), Image.LANCZOS)
        tiles.append(label(ref, t))
    for shot in ORDER:
        if not os.path.exists(os.path.join(RAW, shot + '.png')):
            continue
        im = post(shot)
        im.save(os.path.join(SEC, shot + '.png'))
        pix(im).save(os.path.join(SEC, shot + '-px7.png'))
        done[shot] = im
        tiles.append(label(im.resize((W, H), Image.LANCZOS), titles.get(shot, shot)))
    cols = 3
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new('RGB', (cols * W, rows * H), (8, 12, 9))
    for i, t in enumerate(tiles):
        s.paste(t, ((i % cols) * W, (i // cols) * H))
    s.save(os.path.join(SEC, 'sheet.png'))
    print('sheet', len(tiles), 'tiles')


BG, INK, DIM = (14, 18, 15), (225, 235, 225), (90, 105, 92)
COL = {0: (170, 180, 170), 1: (255, 200, 60), 2: (255, 70, 50), 3: (240, 240, 255), 4: (70, 220, 120)}


def drawings():
    a = R.stair()
    b = R.flood(start=a['end'], heading=a['heading_out'], deck=a['deck'])
    mo = a['mo']
    s0 = a['length']
    # Plan.
    xs = np.concatenate([a['x'], b['x']])
    ys = np.concatenate([a['y'], b['y']])
    x0, x1, y0, y1 = xs.min() - 30, xs.max() + 70, ys.min() - 40, ys.max() + 40
    sc = min(1500 / (x1 - x0), 900 / (y1 - y0))
    Wp, Hp = int((x1 - x0) * sc) + 40, int((y1 - y0) * sc) + 100

    def px(x, y):
        return (20 + (x - x0) * sc, Hp - 30 - (y - y0) * sc)

    im = Image.new('RGB', (Wp, Hp), BG)
    d = ImageDraw.Draw(im)
    c = [R.world(*q) for q in ((-22, -22), (22, -22), (22, 22), (-22, 22), (-22, -22))]
    d.line([px(float(u), float(v)) for u, v in c], fill=DIM, width=2)
    ax, ay, ah, sa = b['axis']
    for side in (-1, 1):
        d.line([px(x - side * 9 * np.sin(h), y + side * 9 * np.cos(h)) for x, y, h, q in zip(ax[::40], ay[::40], ah[::40], sa[::40]) if q < b['door_sa']], fill=DIM, width=1)
    bh = (R.HALL_X - R.ROOM_LEN, 0.0)
    d.rectangle([px(bh[0], 17), px(R.HALL_X, -17)], outline=(255, 90, 60), width=2)
    d.text(px(bh[0] + 2, 34), 'red room', fill=(255, 120, 90), font=F)
    d.text(px(R.HALL_X + 2, -6), 'hall on', fill=DIM, font=F)
    d.text(px(R.DOOR_S - 60, 8), 'lab doors', fill=DIM, font=F)
    for r in (a, b):
        pts = [px(x, y) for x, y in zip(r['x'], r['y'])]
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=COL[int(r['surface'][i])], width=2)
    for s, t in ((b['stop_s'], 'stop'),):
        q = px(np.interp(s, b['fx'], b['x']), np.interp(s, b['fx'], b['y']))
        d.ellipse((q[0] - 5, q[1] - 5, q[0] + 5, q[1] + 5), outline=(255, 255, 255), width=2)
        d.text((q[0] + 8, q[1] - 24), t, fill=INK, font=F)
    d.text((20, 10), f'PLAN. stair {a["length"]:.0f} m, flood {b["length"]:.0f} m. x right, y up.', fill=INK, font=FB)
    for i, (k, t) in enumerate(((0, 'floor'), (1, 'steps'), (2, 'wall'), (3, 'air'), (4, 'water'))):
        d.rectangle((20 + i * 130, 44, 34 + i * 130, 58), fill=COL[k])
        d.text((40 + i * 130, 42), t, fill=INK, font=F)
    im.save(os.path.join(SEC, 'road-plan.png'))
    # Side elevation: height against distance.
    L = a['length'] + b['length']
    W, H = 1700, 620
    zmin = float(min(a['z'].min(), b['z'].min())) - 12
    zmax = 22.0

    def pe(s, z):
        return (60 + s / L * (W - 90), 70 + (zmax - z) / (zmax - zmin) * (H - 110))

    im = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(im)
    for z in range(0, int(zmin) - 1, -25):
        q = pe(0, z)
        d.line([(60, q[1]), (W - 30, q[1])], fill=(34, 42, 36))
        d.text((10, q[1] - 9), str(z), fill=DIM, font=F)
    for r, off in ((a, 0.0), (b, s0)):
        f = r.get('fly', r['z'])
        pts = [pe(off + s, z) for s, z in zip(r['fx'], f)]
        for i in range(len(pts) - 1):
            d.line([pts[i], pts[i + 1]], fill=COL[int(r['surface'][i])], width=3)
    marks = [(2, 40.0), (3, 80.0), (4, R.s_of_side(a, mo['hug'])), (5, a['air'][0][0]), (6, R.s_of_side(a, mo['tight'])), (7, a['length'] * 0.87), (8, s0 + 30.0), (9, s0 + b['stop_s'])]
    marks.insert(0, (1, 10.0))
    for m, s in marks:
        z = float(np.interp(s, a['fx'], a['z'])) if s <= s0 else float(np.interp(s - s0, b['fx'], b['z']))
        q = pe(s, z)
        d.ellipse((q[0] - 6, q[1] - 6, q[0] + 6, q[1] + 6), outline=INK, width=2)
        d.text((q[0] + 6, q[1] - 26), str(m), fill=INK, font=FB)
    q = pe(s0, zmax)
    d.line([q, (q[0], H - 30)], fill=DIM, width=1)
    d.text((q[0] + 6, 44), 'water', fill=DIM, font=F)
    d.text((20, 10), f'SIDE ELEVATION. {a["length"]:.0f} m down {-a["deck"]:.0f} m, then {b["length"]:.0f} m level; moments 1 to 9. x along the road, y height (m).', fill=INK, font=FB)
    im.save(os.path.join(SEC, 'road-elevation.png'))


if __name__ == '__main__':
    sheet()
    drawings()
