"""Draw the concept's traced features over an image, to check a render against the concept (any size; it's fitted to
1280x720): python3 art/guides.py render.png out.png [--guides art/reference/concept-bike-guides.json]
The default guides are the landing shot's (art/reference/concept-guides.json); concept-bike-guides.json traces the bike's
parts. Each feature is labelled."""
import json
import os
import sys

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
COLOURS = {'boxes': (255, 60, 220), 'polygons': (255, 60, 220), 'ellipses': (60, 220, 255), 'lines': (255, 220, 0), 'points': (255, 120, 40)}


def draw(src, out, guides_path=os.path.join(HERE, 'reference', 'concept-guides.json')):
    GUIDES = json.load(open(guides_path))
    w, h = GUIDES['size']
    image = Image.open(src).convert('RGB').resize((w, h))
    d = ImageDraw.Draw(image)
    for name, pts in GUIDES.get('polygons', {}).items():
        d.polygon([tuple(p) for p in pts], outline=COLOURS['polygons'], width=2)
        d.text((pts[0][0] + 4, pts[0][1] - 14), name, fill=COLOURS['polygons'])
    for name, (x0, y0, x1, y1) in GUIDES.get('boxes', {}).items():
        d.rectangle((x0, y0, x1, y1), outline=COLOURS['boxes'], width=2)
        d.text((x0 + 4, y0 + 3), name, fill=COLOURS['boxes'])
    for name, (cx, cy, rx, ry) in GUIDES.get('ellipses', {}).items():
        d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), outline=COLOURS['ellipses'], width=2)
        d.text((cx - rx, cy + ry + 3), name, fill=COLOURS['ellipses'])
    for name, pts in GUIDES.get('lines', {}).items():
        d.line([tuple(p) for p in pts], fill=COLOURS['lines'], width=2)
        d.text((pts[0][0] + 4, pts[0][1] + 3), name, fill=COLOURS['lines'])
    for name, (x, y) in GUIDES.get('points', {}).items():
        d.ellipse((x - 6, y - 6, x + 6, y + 6), outline=COLOURS['points'], width=2)
        d.text((x + 9, y - 6), name, fill=COLOURS['points'])
    image.save(out)


if __name__ == '__main__':
    args = sys.argv[1:]
    if '--guides' in args:
        i = args.index('--guides')
        draw(args[0], args[1], args[i + 1])
    else:
        draw(args[0], args[1])
