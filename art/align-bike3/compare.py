"""Overlay the traced guides on ConceptCam3 / PlazaCam3 renders and lay each beside its concept (also guided).
python3 art/align-bike3/compare.py art/renders/bike3-concept-r1.png r1 [art/renders/bike3-plaza-r1.png]
  -> art/align-bike3/out/r1-overlay.png, r1-compare.png (concept above, render below, guides on both),
     r1-side-by-side.png (no guides), and the same with -plaza for the plaza check.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..'))
from guides import draw  # noqa: E402

OUT = os.path.join(HERE, 'out')
os.makedirs(OUT, exist_ok=True)
REF = os.path.join(HERE, '..', 'reference')
SETS = {
    'city': (os.path.join(HERE, 'concept-bike3-guides.json'), os.path.join(REF, 'concept-hive-city.webp'), (940, 340, 1672, 941)),
    'plaza': (os.path.join(HERE, 'concept-bike3-plaza-guides.json'), os.path.join(REF, 'concept-hive-plaza.webp'), (1050, 460, 1672, 941)),
}


def one(src, tag, which):
    G, concept, box = SETS[which]
    sfx = '' if which == 'city' else '-plaza'
    ov = os.path.join(OUT, f'{tag}{sfx}-overlay.png')
    draw(src, ov, G)
    cg = os.path.join(OUT, f'concept{sfx}-guides.png')
    draw(concept, cg, G)
    a, b = Image.open(cg).crop(box), Image.open(ov).crop(box)
    c = Image.new('RGB', (a.width * 2, a.height))
    c.paste(a, (0, 0))
    c.paste(b, (a.width, 0))
    c.save(os.path.join(OUT, f'{tag}{sfx}-compare.png'))
    r = Image.open(src).convert('RGB').resize((1672, 941)).crop(box)
    k = Image.open(concept).convert('RGB').crop(box)
    s = Image.new('RGB', (k.width * 2, k.height))
    s.paste(k, (0, 0))
    s.paste(r, (k.width, 0))
    s.save(os.path.join(OUT, f'{tag}{sfx}-side-by-side.png'))
    print(os.path.join(OUT, f'{tag}{sfx}-compare.png'))


if __name__ == '__main__':
    one(sys.argv[1], sys.argv[2], 'city')
    if len(sys.argv) > 3:
        one(sys.argv[3], sys.argv[2], 'plaza')
