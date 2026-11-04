"""Warp a ConceptCam5 render onto the concept (concept-map.json) and compare: python3 art/align-bike5/compare.py TAG
  -> art/align-bike5/out/TAG-overlay.png (half and half), TAG-guides.png (the traced guides on each, above and below),
     TAG-side-by-side.png, and for the rider's and the plaza's views TAG-rider.png, TAG-plaza.png beside their concepts.
"""
import json
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, '..')
sys.path.insert(0, ART)
from guides import draw  # noqa: E402

M = json.load(open(os.path.join(HERE, 'concept-map.json')))
G = os.path.join(HERE, 'concept-bike5-guides.json')
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
tag = sys.argv[1]
W, H = M['size']
concept = Image.open(os.path.join(ART, 'reference', 'concept-bike5.png')).convert('RGB')


def warp(src):
    """The ConceptCam5 render (ortho 2.9 m across 1920 px, centred on x 0, z 0.62) in the concept's pixels."""
    im = Image.open(src).convert('RGB')
    m = 2.9 / im.width
    # concept px -> x -> render px: x = 0.78 - (px - p0) * sx; ix = w/2 - x / m (image right is -x)
    ax = M['sx'] / m
    bx = im.width / 2 - (0.78 + M['px_front_axle'] * M['sx']) / m
    # concept py -> z -> render py: z = (g - py) * sz; iy = h/2 - (z - 0.62) / m
    ay = M['sz'] / m
    by = im.height / 2 - (M['py_ground'] * M['sz'] - 0.62) / m
    return im.transform((W, H), Image.AFFINE, (ax, 0, bx, 0, ay, by), Image.BICUBIC)


src = os.path.join(ART, 'renders', f'bike5-concept-{tag}.png')
if os.path.exists(src):
    r = warp(src)
    Image.blend(concept, r, 0.5).save(os.path.join(OUT, f'{tag}-overlay.png'))
    s = Image.new('RGB', (W, H * 2))
    s.paste(concept, (0, 0))
    s.paste(r, (0, H))
    s.save(os.path.join(OUT, f'{tag}-side-by-side.png'))
    tmp = os.path.join(OUT, f'{tag}-warped.png')
    r.save(tmp)
    if os.path.exists(G):
        a, b = os.path.join(OUT, 'concept-guides.png'), os.path.join(OUT, f'{tag}-guides-r.png')
        draw(os.path.join(ART, 'reference', 'concept-bike5.png'), a, G)
        draw(tmp, b, G)
        s = Image.new('RGB', (W, H * 2))
        s.paste(Image.open(a), (0, 0))
        s.paste(Image.open(b), (0, H))
        s.save(os.path.join(OUT, f'{tag}-guides.png'))
        os.remove(b)
    os.remove(tmp)
for view, ref, box in (('rider', 'concept-core-servers.png', (0, 560, 1672, 941)), ('plaza', 'concept-core-plaza.png', (1000, 450, 1672, 941))):
    p = os.path.join(ART, 'renders', f'bike5-{view}-{tag}.png')
    if not os.path.exists(p):
        continue
    if view == 'rider':
        k = Image.open(os.path.join(ART, 'reference', ref)).convert('RGB').crop(box)
        q = Image.open(p).convert('RGB').resize((1672, 941)).crop(box)
        s = Image.new('RGB', (k.width, k.height * 2))
        s.paste(k, (0, 0))
        s.paste(q, (0, k.height))
    else:
        k = Image.open(os.path.join(ART, 'reference', ref)).convert('RGB').crop(box)
        q = Image.open(p).convert('RGB')
        q = q.resize((int(q.width * k.height / q.height), k.height))
        s = Image.new('RGB', (k.width + q.width, k.height))
        s.paste(k, (0, 0))
        s.paste(q, (k.width, 0))
    s.save(os.path.join(OUT, f'{tag}-{view}.png'))
print(OUT)
