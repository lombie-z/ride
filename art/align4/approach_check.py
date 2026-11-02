"""Check the approach (City4.ApproachCam's render) against concept-transition-desert: its guides, traced by hand off a
gridded crop of the concept, drawn over both, side by side (out/approach-ROUND-compare.png).

  python3 art/align4/approach_check.py ROUND      (art/build-city4.py runs it after rendering)

The approach is a mood check, not a fit: the concept's chase camera sits behind the rider (the rider and bike aren't
in our render), and its facility is drawn far bigger than one ~2.6 km down the road can be. The guides say where things
should sit: the horizon and the road's vanishing point, the storm's top edge, the facility, the servers on the right
(the big hero one close by, the mid ones in the dunes), and zone 3's city on the left (not ours: empty in the render).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

from common import APPROACH_FEATURES, CONCEPT_APPROACH, H, OUT, ROOT, W, concept_rgb, save_json

ROUND = sys.argv[1] if len(sys.argv) > 1 else 'r0'
G = {
    'horizon': 345.0,
    'vanishing': [470.0, 345.0],
    'road_centre': [[600.0, 700.0], [482.0, 420.0]],
    'storm_edge': [[600, 250], [640, 215], [700, 172], [800, 125], [900, 100], [1000, 108], [1100, 130]],
    'boxes': {'facility': [515, 180, 690, 345], 'hero_server': [1055, 30, 1280, 400], 'server_1': [800, 255, 912, 352],
              'server_2': [640, 332, 697, 388], 'server_3': [995, 282, 1035, 330], 'zone3_city': [0, 0, 470, 720]},
}


def draw(d, col):
    d.line([(0, G['horizon']), (W, G['horizon'])], fill=col, width=1)
    vx, vy = G['vanishing']
    d.ellipse((vx - 5, vy - 5, vx + 5, vy + 5), outline=col, width=2)
    d.line([tuple(p) for p in G['road_centre']], fill=col, width=2)
    d.line([tuple(p) for p in G['storm_edge']], fill=col, width=2)
    for k, b in G['boxes'].items():
        d.rectangle(b, outline=col, width=1)
        d.text((b[0] + 3, b[1] + 3), k, fill=col)


def main():
    save_json(APPROACH_FEATURES, G)
    con = Image.fromarray((concept_rgb(CONCEPT_APPROACH) * 255).astype(np.uint8))
    draw(ImageDraw.Draw(con), (255, 0, 255))
    rp = os.path.join(ROOT, 'art', 'renders', f'city4-approach-{ROUND}.png')
    ren = Image.open(rp).convert('RGB').resize((W, H)) if os.path.exists(rp) else Image.new('RGB', (W, H))
    d = ImageDraw.Draw(ren)
    draw(d, (255, 0, 255))
    d.text((8, H - 16), f'{ROUND} approach  magenta = concept-transition-desert guides', fill=(255, 0, 255))
    both = Image.new('RGB', (W, H * 2))
    both.paste(con, (0, 0))
    both.paste(ren, (0, H))
    both.save(os.path.join(OUT, f'approach-{ROUND}-compare.png'))
    print('approach compare', os.path.join(OUT, f'approach-{ROUND}-compare.png'))


if __name__ == '__main__':
    main()
