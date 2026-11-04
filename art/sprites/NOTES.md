# Core zone sprites

Five flipbooks for the gate, lab, server hall and chamber, to replace the flat cards. Nothing from outside: all generated here, so no LICENSES.md.

Each sheet is 1024 x 1024, 8-bit greyscale, 8 x 8 frames of 128 px, read left to right, top to bottom, 64 frames. Grey is density, in linear: load with `NoColorSpace`, never sRGB.

## Using them

Sample one channel as density `d`, then for premultiplied blending (One, OneMinusSrcAlpha) output `rgb = tint * d * opacity`, `a = d * opacity`. For additive, output the same rgb and leave alpha out.

Give each card its own start frame and scale, and don't repeat one on a neighbouring card. Below about 20 fps, sample two frames and mix them, or the steps show. Don't mix on sand-gust: it doubles the grit.

No mipmaps (`LinearFilter`, `generateMipmaps = false`). The gutter is 7 px, which only survives down to mip 2 before frames bleed into each other. All of these are soft apart from sand-gust, which should fade out with distance rather than shimmer.

Where a card meets the floor or a wall, a soft-particle depth fade will hide the line better than anything in the sheet can.

The opacities below are starting points from laying frames over the concepts, not from the site's own light. Bloom and the grade will change them.

**steam-billow.** Floor steam at the feet of the tanks. Square card, premultiplied, tint #d6ecda, opacity 0.5-0.7, 16-20 fps. Sits a little above the floor: its base is a long soft fade, so let that overlap the ground. Flip in x freely.

**fog-bank.** The low green bank along the road in the server hall. 4:1 card, and only right at 4:1 (in the raw frame it looks like grass). Premultiplied, or additive at much lower opacity; tint #54965c, opacity 0.35-0.6, 12 fps. It drifts towards +u at about 1.3 px a frame (1% of the card), about 5 s a loop. Flipping u reverses the drift, so flip by which way the air should move, not at random.

**sand-gust.** Grit across the road at the gate. 3:1 card (authored for it, dashes are short in the raw frame). Premultiplied, tint #cd8c4c, opacity 0.6-0.9, 24-30 fps, no frame mixing. Wind blows towards +u: the front crosses the frame 3 times a loop, about 6 px a frame, and the grit moves slower so it falls behind and tears up. Layer several, offset in time, some thin and far away.

**steam-rise.** Columns in the chamber. 1:1.5 to 1:2 card, premultiplied, tint #d6ecda, opacity 0.4-0.6, 16-20 fps. The source is near the bottom of the frame and tapers out of nothing, so hide its foot behind something or start it against a dark rack.

**light-shaft.** The beam from the oculus. 1:2 card, turn about the vertical only (not a full billboard), additive, tint #cdf0d6, opacity 0.4-0.8, 10-12 fps with frame mixing, so about 6 s a loop. The top of the frame goes at the oculus. It's slow on purpose: motes sink about 0.3 px a frame.

## How they're made

`sim-steam.py` is a small 3D smoke solver (semi-Lagrangian velocity, MacCormack density, FFT pressure, vorticity confinement) in numpy and numba. steam-billow and steam-rise run on a 384 x 384 x 192 grid, fog-bank on 512 x 128 x 128 with real wind shear. Depth is integrated along the view, through a saturating curve, then area-averaged to 128. Their loops come from crossfading the frames after the loop's end back under its first 32 frames, equal-power, so frame 63 runs straight on into frame 0. Fog also slides sideways at a set rate.

`build-sprites.py` tones those, and builds sand-gust (4200 motion-blurred dashes over a torn haze) and light-shaft (beam profile, slow noise, 42 motes) directly. Those two have only whole cycles per loop, so they loop exactly.

`check-sprites.py` writes `contact-*.png`, `loop-check.png` and `qa.json`.

    python3 art/sprites/sim-steam.py billow <cache>    # and rise, fog; each 2-6 min on 14 cores
    python3 art/sprites/build-sprites.py <cache>
    python3 art/sprites/check-sprites.py

## Numbers

Step sizes are mean absolute difference between frames, out of 255. The seam is frame 63 to frame 0. "Range" is the smallest and largest of the other 63 steps.

    sheet           KB   seam   mean step   seam/mean   range        outer 4 px max   first lit px   density swing
    steam-billow   217   1.01     1.06        0.96      0.80-1.35          0               9              5%
    fog-bank       222   2.52     2.34        1.08      1.76-2.65          0               8              8%
    sand-gust      117   3.29     3.46        0.95      2.95-4.24          0               9             19%
    steam-rise     191   1.13     1.29        0.88      1.15-1.44          0              12              6%
    light-shaft    164   0.25     0.24        1.04      0.21-0.29          0               9              0.3%

Outer 4 px max is over all 64 frames: true black. First lit px is the closest any frame's non-zero pixel ever gets to the frame's edge. Fog's seam is a little over its mean because the crossfaded frames step slightly less than the plain ones; it's still inside the range of ordinary steps.

## Smaller formats

    sheet          PNG KB   WebP lossless   WebP q80
    steam-billow     217        186            26
    fog-bank         222        187            31
    sand-gust        117        112            37
    steam-rise       191        171            35
    light-shaft      164        135            23
    total            911        791           152

Lossy WebP at q80 (`cwebp -q 80 -m 6 -sharp_yuv`) is 3 to 8 times smaller and looks fine: mean error under 1 level, and the seam holds. It does lift the outer 4 px to 1 or 2 levels, so a shader using it should subtract about 2/255 from `d` before clamping, or the card outline could just show under bloom. These weren't kept, only measured.

KTX2 not measured: toktx and basisu aren't installed. It wouldn't win on download against q80 WebP, but it would on memory: PNG or WebP decode to 4 MB RGBA per sheet unless re-uploaded as R8. Five sheets at 20 MB may be worth the step if memory is tight; check UASTC rather than ETC1S, which tends to block up soft gradients.

## What's weak

- None of it has been seen moving, or in three. Motion is judged from frame strips, step sizes and the space-time slices in `loop-check.png`.
- sand-gust is the weakest. On a 3:1 card it reads as a long streak, but it's more a grainy haze than separate grains, and when a front has just come in, the streak is short for a few frames (19% swing in density).
- steam-billow's silhouette is a bit squared-off at the top for its first frames, and a slightly heart-shaped base. Varied start frames and flips should hide it.
- fog-bank's wisps are soft humps more than thin curling tendrils. In the sim they're averaged by the depth they're seen through.
- The sim sheets' crossfades overlay two states of the smoke over 32 of the 64 frames. No visible step in the numbers, but a slight softening there is possible.
