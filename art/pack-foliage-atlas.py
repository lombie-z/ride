"""Pack the foliage sprites (art/bake-foliage-sprites.py) into one atlas for the site: each sprite cropped to its
plant, scaled to fill a square cell's height (or width), standing on the cell's floor and centred. Writes
public/textures/landing/foliage-atlas.webp and foliage-atlas.json (per cell: name, and the plant's width / height).

Run: python3 art/pack-foliage-atlas.py <sprites dir>
"""
import json
import os
import sys

from PIL import Image

SPRITES = sys.argv[1]
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
OUT = os.path.join(ROOT, 'public', 'textures', 'landing')
# The trees only: Poly Haven's shrub scans are sparse weeds that don't read as the reference's bushes.
NAMES = [f'{a}_{v}' for a in ('island_tree_01', 'island_tree_01_pink', 'island_tree_02') for v in range(3)]
CELL, COLS = 512, 3

rows = (len(NAMES) + COLS - 1) // COLS
atlas = Image.new('RGBA', (CELL * COLS, CELL * rows), (0, 0, 0, 0))
cells = []
for i, name in enumerate(NAMES):
    im = Image.open(os.path.join(SPRITES, name + '.png')).convert('RGBA')
    im = im.crop(im.getchannel('A').getbbox())
    scale = CELL / max(im.width, im.height)
    im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.LANCZOS)
    x0, y0 = (i % COLS) * CELL, (i // COLS) * CELL
    atlas.paste(im, (x0 + (CELL - im.width) // 2, y0 + CELL - im.height), im)
    cells.append({'name': name, 'aspect': round(im.width / im.height, 3), 'fill': round(max(im.width, im.height) / CELL, 3)})

atlas.save(os.path.join(OUT, 'foliage-atlas.webp'), quality=85, method=6)
with open(os.path.join(OUT, 'foliage-atlas.json'), 'w') as fh:
    json.dump({'cols': COLS, 'rows': rows, 'cells': cells}, fh, indent=1)
print('packed', len(cells), 'into', atlas.size)
