"""How the new sections take their assets: by name, one at a time, with the blockout standing in until one lands.

    kit_piece = assetkit.use(kit, 'stair_flight', fallback=lambda: mesh)
    kit_piece.put(loc, rot=(rx, ry, rz) | Matrix, scale=1.0, grp='Stair')

If art/out/assets/<name>.glb exists it's imported (see art/core/ASSETS.md for the contract each must meet), its meshes
shared by every placement so it exports as GPU instances; if not, fallback() makes the grey stand-in. Same origin, same
axes, either way, so nothing else changes when one lands. Every placement's counted for ASSETS.md (`counts()`).
"""
import os
import re

import bpy
from mathutils import Euler, Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
ASSETS = os.path.join(ROOT, 'art', 'out', 'assets')
_pieces = {}
_counts = {}


def path(name):
    return os.path.join(ASSETS, name + '.glb')


def have(name):
    return os.path.exists(path(name)) and not os.environ.get('SECTIONS_BLOCKOUT')


def _same_material(me):
    """A glb's City5Concrete comes in as City5Concrete.001: the kit's own, or the first asset's, stands (same name, same
    material: the contract)."""
    for i, m in enumerate(me.materials):
        base = re.sub(r'\.\d{3}$', '', m.name) if m else None
        if m and base != m.name and base in bpy.data.materials:
            me.materials[i] = bpy.data.materials[base]


def _import(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=path(name))
    new = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()
    parts = []
    for o in new:
        if o.type == 'MESH':
            _same_material(o.data)
            parts.append((o.data, o.matrix_world.copy(), o.name))
    for o in new:
        bpy.data.objects.remove(o)
    if not parts:
        raise RuntimeError(f'{name}.glb has no meshes')
    return parts


class Piece:
    def __init__(self, kit, name, parts, source):
        self.kit, self.name, self.parts, self.source = kit, name, parts, source
        self.tris = sum(kit.tris(me) for me, _m, _n in parts)

    def put(self, loc, rot=(0.0, 0.0, 0.0), scale=1.0, grp='Parts', named=None):
        kit = self.kit
        R = rot if isinstance(rot, Matrix) else Euler(rot, 'XYZ').to_matrix()
        S = Matrix.Diagonal((*(scale if not isinstance(scale, (int, float)) else (scale,) * 3), 1.0))
        M = Matrix.Translation(Vector(loc)) @ R.to_4x4() @ S
        out = []
        for me, local, part in self.parts:
            o = bpy.data.objects.new(named or f'{kit.PREFIX}.{self.name}.i', me)
            bpy.context.scene.collection.objects.link(o)
            o.parent = kit.group(grp)
            o.matrix_basis = M @ local
            out.append(o)
        c = _counts.setdefault(self.name, {'n': 0, 'tris': self.tris, 'source': self.source, 'groups': []})
        c['n'] += 1
        if grp not in c['groups']:
            c['groups'].append(grp)
        return out


def use(kit, name, fallback):
    """The piece by name: its glb if it's landed, else the blockout's."""
    if name in _pieces:
        return _pieces[name]
    if have(name):
        p = Piece(kit, name, _import(name), 'asset')
    else:
        p = Piece(kit, name, [(fallback(), Matrix.Identity(4), name)], 'blockout')
    _pieces[name] = p
    return p


def counts():
    return _counts


def reset():
    _pieces.clear()
    _counts.clear()
