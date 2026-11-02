"""Overlay the traced guides on a ConceptCam4 render and lay it beside the concept (also guided).
python3 art/align-bike4/compare.py art/renders/bike4-concept-r1.png r1
  -> art/align-bike4/out/r1-overlay.png, r1-compare.png (guided concept above, guided render below), r1-side-by-side.png
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from guides import draw  # noqa: E402

G = os.path.join(HERE, 'concept-bike4-guides.json')
CONCEPT = os.path.join(HERE, '..', 'reference', 'concept-desert.webp')
OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
src, tag = sys.argv[1], sys.argv[2]
ov = os.path.join(OUT, f'{tag}-overlay.png')
draw(src, ov, G)
cg = os.path.join(OUT, 'concept-guides.png')
draw(CONCEPT, cg, G)
box = (900, 360, 1672, 941)  # the bike
a, b = Image.open(cg).crop(box), Image.open(ov).crop(box)
c = Image.new('RGB', (a.width * 2, a.height))
c.paste(a, (0, 0))
c.paste(b, (a.width, 0))
c.save(os.path.join(OUT, f'{tag}-compare.png'))
# plain side by side without guides
r = Image.open(src).convert('RGB').resize((1672, 941)).crop(box)
k = Image.open(CONCEPT).convert('RGB').crop(box)
s = Image.new('RGB', (k.width * 2, k.height))
s.paste(k, (0, 0))
s.paste(r, (k.width, 0))
s.save(os.path.join(OUT, f'{tag}-side-by-side.png'))
print(ov, os.path.join(OUT, f'{tag}-compare.png'))
