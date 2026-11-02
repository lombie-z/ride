"""Draw the fitted ConceptCam4's projection of the tyres, shoulder and fit points over the guided concept:
python3 art/align-bike4/preview_fit.py -> out/fit-preview.png"""
import json, os
import numpy as np
from PIL import Image, ImageDraw
import fit_camera as F
HERE = os.path.dirname(os.path.abspath(__file__))
C = json.load(open(os.path.join(HERE, 'concept-cam4.json')))
eye, look, fov = np.array(C['location']), np.array(C['look']), C['vfov']
im = Image.open(os.path.join(HERE, 'out', 'concept-guides.png')).convert('RGB')
d = ImageDraw.Draw(im)
for P, col in ((F.PTS['rear'], (0, 255, 120)), (F.PTS['front'], (0, 255, 120)), (F.SH, (255, 0, 0))):
    for u, v in F.project(P, eye, look, fov)[::3]:
        d.point((u, v), fill=col)
for name, (P, _) in F.POINTS.items():
    u, v = F.project(F.local_to_world(np.array(P))[None], eye, look, fov)[0]
    d.ellipse((u - 5, v - 5, u + 5, v + 5), outline=(0, 255, 0), width=2)
im.crop((900, 350, 1672, 941)).save(os.path.join(HERE, 'out', 'fit-preview.png'))
