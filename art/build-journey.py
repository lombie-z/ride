"""Key the journey camera (JourneyCam) the scroll runs along: frame 0 is the hero, the last frame is the city.
Re-runnable; it replaces the keys. Shape it by moving the SHOTS below (or nudge keys in Blender), then re-export.
Run inside Blender with art/micro-biome.blend open:  exec(open('<repo>/art/build-journey.py').read())

The path is a few composed shots joined by one smooth curve (Catmull-Rom through the eye points and, separately,
through the look-at points), so the camera never lurches. One crane move:
  0-80     Open up: from the blog's near-orthographic hero, a dolly zoom (lens widens as the camera closes in, so the
           biome holds its size).
  80-300   Drop just below the planter's lip beside the falls and tilt up: the oil pours down from the floating toy.
  300-760  Pull straight back and down from the planter to the freeway, levelling out low beside the bike (the planter
           and its falls stay in view ahead, between the road and the city).
  760-920  Hold on the landing (the shot matched to art/reference/concept-green-city).
"""
import math

import bpy
from mathutils import Vector

scene = bpy.context.scene
F_OPEN, F_END = 80, 920
HERO_TARGET = Vector((0, 0, 0.92))
HERO_DIRECTION = Vector((-1, -1, 0.75)).normalized()  # the blog's view (PreviewCam)
HERO_FOV, OPEN_FOV = 6.0, 38.0
# Height of the view at the target, in metres: the hero shows the biome about as big as the blog does.
HERO_VIEW, OPEN_VIEW = 4.6, 3.2
OPEN_TARGET = Vector((0, 0, 0.45))

# (frame, eye, look-at, vertical FOV) for each composed shot after the opening beat. Pool surface is at z -11; the
# main falls leave the planter at A (0.17, -0.5), B (-0.5, 0.14), C (0.5, -0.24) and braid from z -2.1 to -7.
SHOTS = [
    # Drop just below the planter's lip beside the falls (on the side the hero looks from), tilting up: the black oil
    # pours down at you from the floating toy.
    (200, Vector((-2.297, -2.507, -1.5)), Vector((0.0, 0.0, 0.3)), 46.0),
    (300, Vector((-3.783, -4.129, -2.8)), Vector((0.0, 0.0, -0.6)), 45.0),
    # Then one straight pull back and down along the line from the planter to the landing (art/build-city.py places the
    # landing so it faces the planter), levelling out at the bike: the planter and its falls stay ahead, between the
    # road and the city.
    (460, Vector((-10.134, -11.059, -4.6)), Vector((0.787, 0.278, -3.399)), 44.0),
    (620, Vector((-24.321, -26.542, -8.4)), Vector((2.886, 1.02, -6.695)), 43.5),
    # The landing (art/build-city.py EYE, LOOK, FOV: fitted to the concept by art/align): low beside the bike, looking
    # across the road to the city.
    (760, Vector((-37.1575, -40.5503, -10.4121)), Vector((5.2472, 1.8544, -8.4911)), 42.98),
    # Then hold on it (a barely-there drift back, so it stays alive).
    (840, Vector((-37.225, -40.624, -10.4121)), Vector((5.2472, 1.8544, -8.4911)), 42.68),
    (920, Vector((-37.279, -40.683, -10.4121)), Vector((5.2472, 1.8544, -8.4911)), 42.38),
]
# Sun, warm light and rainbow come in below the clouds.
F_SUN_IN, F_SUN_FULL = 275, 380
F_BOW_IN, F_BOW_FULL = 640, 720


def ease(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, t):
    return a + (b - a) * t


def dwell(t):
    """Nearly even travel (it's a fall, not a tour), easing only slightly through each shot."""
    return lerp(t, ease(t), 0.15)


def opening(f):
    u = dwell(f / F_OPEN)
    fov = lerp(HERO_FOV, OPEN_FOV, u)
    distance = lerp(HERO_VIEW, OPEN_VIEW, u) / (2 * math.tan(math.radians(fov / 2)))
    elevation = lerp(math.asin(HERO_DIRECTION.z), math.radians(14), u)
    target = HERO_TARGET.lerp(OPEN_TARGET, u)
    az = math.radians(-135)
    direction = Vector((math.cos(az) * math.cos(elevation), math.sin(az) * math.cos(elevation), math.sin(elevation)))
    return target + direction * distance, target, fov


def catmull_rom(p0, p1, p2, p3, t):
    """Centripetal Catmull-Rom between p1 and p2 (no loops or overshoot at tight corners)."""

    def knot(a, b, k):
        return k + max((b - a).length, 1e-4) ** 0.5

    t0 = 0.0
    t1 = knot(p0, p1, t0)
    t2 = knot(p1, p2, t1)
    t3 = knot(p2, p3, t2)
    u = lerp(t1, t2, t)
    a1 = p0 * ((t1 - u) / (t1 - t0)) + p1 * ((u - t0) / (t1 - t0))
    a2 = p1 * ((t2 - u) / (t2 - t1)) + p2 * ((u - t1) / (t2 - t1))
    a3 = p2 * ((t3 - u) / (t3 - t2)) + p3 * ((u - t2) / (t3 - t2))
    b1 = a1 * ((t2 - u) / (t2 - t0)) + a2 * ((u - t0) / (t2 - t0))
    b2 = a2 * ((t3 - u) / (t3 - t1)) + a3 * ((u - t1) / (t3 - t1))
    return b1 * ((t2 - u) / (t2 - t1)) + b2 * ((u - t1) / (t2 - t1))


open_eye, open_target, _ = opening(F_OPEN)
before_eye, before_target, _ = opening(F_OPEN * 0.6)
KEYS = [(F_OPEN, open_eye, open_target, OPEN_FOV), *SHOTS]
EYES = [before_eye, *[k[1] for k in KEYS]]
TARGETS = [before_target, *[k[2] for k in KEYS]]
# Phantom end points continue the last segment's direction.
EYES.append(EYES[-1] * 2 - EYES[-2])
TARGETS.append(TARGETS[-1] * 2 - TARGETS[-2])


def shot(f):
    """Camera position, look-at point and vertical FOV (degrees) at frame f."""
    if f <= F_OPEN:
        return opening(f)
    for i in range(len(KEYS) - 1):
        f0, _, _, fov0 = KEYS[i]
        f1, _, _, fov1 = KEYS[i + 1]
        if f <= f1:
            t = dwell((f - f0) / (f1 - f0))
            eye = catmull_rom(EYES[i], EYES[i + 1], EYES[i + 2], EYES[i + 3], t)
            target = catmull_rom(TARGETS[i], TARGETS[i + 1], TARGETS[i + 2], TARGETS[i + 3], t)
            return eye, target, lerp(fov0, fov1, ease(t))
    return KEYS[-1][1], KEYS[-1][2], KEYS[-1][3]


cam = bpy.data.objects.get('JourneyCam')
if not cam:
    cam = bpy.data.objects.new('JourneyCam', bpy.data.cameras.new('JourneyCam'))
    scene.collection.objects.link(cam)
cam.animation_data_clear()
cam.data.animation_data_clear()
cam.rotation_mode = 'QUATERNION'
cam.data.type = 'PERSP'
cam.data.sensor_fit = 'VERTICAL'
cam.data.sensor_height = 24
cam.data.clip_start = 0.05
cam.data.clip_end = 200
scene.frame_start, scene.frame_end = 0, F_END

previous = None
for f in range(F_END + 1):
    eye, target, fov = shot(f)
    q = (target - eye).to_track_quat('-Z', 'Y')
    # Keep neighbouring keys on the same side of the quaternion double cover so it never spins the long way.
    if previous is not None and previous.dot(q) < 0:
        q.negate()
    previous = q
    cam.location = eye
    cam.rotation_quaternion = q
    cam.data.lens = 12 / math.tan(math.radians(fov / 2))
    cam.keyframe_insert('location', frame=f)
    cam.keyframe_insert('rotation_quaternion', frame=f)
    cam.data.keyframe_insert('lens', frame=f)


# --- What changes along the way ---------------------------------------------------------------------------------------


def key_value(socket, frames_values):
    for frame, value in frames_values:
        socket.default_value = value
        socket.keyframe_insert('default_value', frame=frame)


def key_hidden(obj, first_visible):
    obj.animation_data_clear()
    for frame, hidden in ((0, True), (first_visible - 1, True), (first_visible, False)):
        obj.hide_render = hidden
        obj.keyframe_insert('hide_render', frame=frame)


sun = bpy.data.objects['Sun']
key_hidden(sun, F_SUN_IN)
sun_mat = bpy.data.materials['Sun']
sun_mat.node_tree.animation_data_clear()
key_value(sun_mat.node_tree.nodes['Emission'].inputs['Strength'], ((F_SUN_IN, 0.0), (F_SUN_FULL, 8.0)))

bow = bpy.data.objects['Rainbow']
key_hidden(bow, F_BOW_IN)
bow_mat = bpy.data.materials['Rainbow']
bow_mat.node_tree.animation_data_clear()
# The 0.8 multiplier on the bow's opacity (labelled 'bow' in build-sky.py).
strength = next(n for n in bow_mat.node_tree.nodes if n.label == 'bow')
key_value(strength.inputs[1], ((F_BOW_IN, 0.0), (F_BOW_FULL, 0.8)))

# The studio key light warms as the sun comes out.
key = bpy.data.objects['StudioKey'].data
key.animation_data_clear()
for frame, colour in ((F_SUN_IN, (1.0, 1.0, 1.0)), (F_SUN_FULL, (1.0, 0.84, 0.66))):
    key.color = colour
    key.keyframe_insert('color', frame=frame)
