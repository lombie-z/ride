"""Overlay the traced guides on a ConceptCam2 render and lay it side by side with the concept (also guided).
python3 art/align-bike2/compare.py art/renders/bike2-concept-r1.png r1   -> art/align-bike2/out/r1-overlay.png, r1-compare.png
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from guides import draw  # noqa: E402

G = os.path.join(HERE, 'concept-bike2-guides.json')
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
src, tag = sys.argv[1], sys.argv[2]
ov = os.path.join(OUT, f'{tag}-overlay.png')
draw(src, ov, G)
cg = os.path.join(OUT, 'concept-guides.png')
draw(os.path.join(HERE, '..', 'reference', 'concept-chrome-city.webp'), cg, G)
a, b = Image.open(cg), Image.open(ov)
box = (60, 300, 1180, 920)  # the bike
a, b = a.crop(box), b.crop(box)
c = Image.new('RGB', (a.width, a.height * 2))
c.paste(a, (0, 0))
c.paste(b, (0, a.height))
c.save(os.path.join(OUT, f'{tag}-compare.png'))
# plain side by side without guides
r = Image.open(src).convert('RGB').resize((1672, 941)).crop(box)
k = Image.open(os.path.join(HERE, '..', 'reference', 'concept-chrome-city.webp')).convert('RGB').crop(box)
s = Image.new('RGB', (k.width * 2, k.height))
s.paste(k, (0, 0))
s.paste(r, (k.width, 0))
s.save(os.path.join(OUT, f'{tag}-side-by-side.png'))
print(ov, os.path.join(OUT, f'{tag}-compare.png'))
