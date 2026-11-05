"""An asset script's shape, runnable: copies of this are art/core/assets/<name>.py. Run with ASSET_NAME=<name> to try the
pipeline; the real one names its asset itself. The piece's origin and axes must be the ones its row in ASSETS.md gives."""
import math
import os
import sys

import bmesh

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402

NAME = os.environ.get('ASSET_NAME', '_template')
kit = A.begin()
bm = bmesh.new()
kit.lathe(bm, [(0.65, -0.5), (0.65, 3.8)], seg=12)
mat = kit.material(f'{kit.PREFIX}TemplatePipe', (0.3, 0.3, 0.28), 0.45, 0.5, tex='rust')
me = kit.mesh_from(NAME, bm, [mat], smooth=True)
kit.box_uvs(me, 0.25)
kit.bake_light(me, [((1.5, -1.5, 3.0), (1.0, 0.1, 0.05), 3.0, 1.0)], ambient=(0.45, 0.47, 0.45))
A.obj(me)
_ = math
A.finish(kit, NAME, budget=300, look_at=(0, 0, 1.6))
