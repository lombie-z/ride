"""Renders one group's module alone: blender --background --factory-startup --python art/core/preview.py -- <module> <shot> [tag]
(the module's SHOTS = {name: (eye, look, fov)}, in the city's frame). Writes art/renders/core-<module>-<shot>-<tag>.png."""
import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.dont_write_bytecode = True
import kit  # noqa: E402

args = sys.argv[sys.argv.index('--') + 1:]
name, shot = args[0], args[1]
tag = args[2] if len(args) > 2 else 'r0'
kit.begin()
mod = importlib.import_module(name)
pieces = mod.build(kit)
mod.place(kit, pieces)
for extra in getattr(mod, 'WITH', []):  # other groups' modules to show alongside (their files, if they exist yet)
    try:
        other = importlib.import_module(extra)
        other.place(kit, other.build(kit))
    except ModuleNotFoundError:
        pass
eye, look, fov = mod.SHOTS[shot]
out = os.path.join(kit.RENDERS, f'core-{name}-{shot}-{tag}.png')
kit.render(eye, look, fov, out)
print('rendered', out)
