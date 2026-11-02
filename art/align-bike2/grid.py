"""Gridded crop of the concept for hand tracing: python3 grid.py x0 y0 x1 y1 scale out.png [image]"""
import sys
from PIL import Image, ImageDraw
x0, y0, x1, y1 = map(int, sys.argv[1:5]); sc = float(sys.argv[5]); out = sys.argv[6]
src = sys.argv[7] if len(sys.argv) > 7 else 'art/reference/concept-chrome-city.webp'
im = Image.open(src).convert('RGB').crop((x0, y0, x1, y1))
im = im.resize((int((x1 - x0) * sc), int((y1 - y0) * sc)), Image.LANCZOS)
d = ImageDraw.Draw(im)
step = 25 if sc >= 1.5 else 50
for x in range((x0 // step + 1) * step, x1, step):
    X = (x - x0) * sc; c = (255, 255, 0) if x % 100 == 0 else (0, 255, 255)
    d.line([(X, 0), (X, im.height)], fill=c, width=1); d.text((X + 2, 2), str(x), fill=c)
for y in range((y0 // step + 1) * step, y1, step):
    Y = (y - y0) * sc; c = (255, 255, 0) if y % 100 == 0 else (0, 255, 255)
    d.line([(0, Y), (im.width, Y)], fill=c, width=1); d.text((2, Y + 2), str(y), fill=c)
im.save(out)
