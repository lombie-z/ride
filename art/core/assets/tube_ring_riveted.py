"""tube_ring_riveted: tube_ring_8's size, origin and ends (see that file), in riveted steel plates. The two tile with each other.
Its bake has a little of the red room's light along the low walls: it's the ring for near the bulkhead."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as A  # noqa: E402
import _mats  # noqa: E402
import tube_ring_8 as T  # noqa: E402

NAME = 'tube_ring_riveted'

if __name__ == '__main__':
    kit = A.begin()
    m = _mats.mats(kit)
    A.obj(T.build(kit, m, riveted=True, name=NAME))
    A.finish(kit, NAME, budget=1100, eye=(-0.5, -4.5, 1.45), look_at=(5.0, 8.5, 6.0), fov=70.0)
