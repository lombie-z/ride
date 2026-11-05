# Stair and tunnel effects

All generated here by `build-fx.py`, nothing from outside, so there are no licences to record. Poly Haven and ambientCG have no water surface (searches find only ice, foam and wet ground) and no flipbooks. Kenney's Smoke Particles and Particle Pack are CC0 but their pages list no spray, sparks or drips; they weren't downloaded.

    python3 -I art/core/fx/build-fx.py [out]

**water-normal.png.** 512 x 512 RGB, tiling, OpenGL/three convention (green up the tile). Load with `NoColorSpace`, `RepeatWrapping`. Scroll two copies at different scales and speeds; the sharp glints come from a high specular power on the crests. Scale `normalScale` to taste.

**Flipbooks.** Same format as `art/sprites` (see its NOTES.md): 1024 x 1024, 8-bit greyscale, 8 x 8 frames of 128 px, left to right, top to bottom, 64 frames. Grey is density, in linear, `NoColorSpace`, no mipmaps. The outer 4 px of every frame is true black.

- **spray.png.** One shot. Water thrown up and out to +u from the lower left: flip in u for the other side of the bike. Premultiplied, tint near white, or additive with the lamps' colours for the far side. About 30 fps.
- **steam-burst.png.** One shot. Comes out of the bottom centre, billows, gone by frame 63. Premultiplied, tint #d6ecda, 24-30 fps. Six layered planes of a small 2D smoke sim.
- **sparks.png.** One shot, starts on a flash at frame 0. Additive, tint a hot orange, 30 fps. Falls, with one bounce at about 86% down the frame.
- **drips.png.** A loop: whole cycles, so frame 63 runs on to frame 0. Beads swell along the top and drop. Additive or premultiplied, tint a pale reflection colour, 16-20 fps. The card's top goes against the pipe or ceiling.

Checked over black and at 1/7. Not seen moving, or in three.
