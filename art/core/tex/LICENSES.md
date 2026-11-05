# Core texture sources

Everything here derives from Poly Haven diffuse maps (1k JPG), all CC0: no attribution required (https://polyhaven.com/license). Each file below is a composite, downsampled to 512 x 512 sRGB JPEG. The generated parts are ours and also CC0.

## tile.jpg

White tiles, 8 across (0.6 m each at 4.8 m an image). The tile grid, grout, per-tile variation and the placement of the rust runs are generated; the rest comes from the sources.

- rusty_metal_02, Rob Tuytel, CC0, https://polyhaven.com/a/rusty_metal_02: orange mask, repeated 4 x 4, as rust flecks around tile edges.
- rusty_metal_05, Amal Kumar, CC0, https://polyhaven.com/a/rusty_metal_05: high-passed, breaks up the runs.
- rust_coarse_01, Dimitrios Savva and Rico Cilliers, CC0, https://polyhaven.com/a/rust_coarse_01: retinted, the colour of the rust.
- concrete_wall_007, Dario Barresi, Rico Cilliers and Charlotte Baglioni, CC0, https://polyhaven.com/a/concrete_wall_007: high-passed, faint glaze surface.
- concrete_wall_006, Dario Barresi and Charlotte Baglioni, CC0, https://polyhaven.com/a/concrete_wall_006: smeared down, water stains.
- dirty_concrete, Rob Tuytel, CC0, https://polyhaven.com/a/dirty_concrete: darkening only, grime by tile and faint blotches.

## rust.jpg

Rusted plate. No riveted CC0 source was found on Poly Haven, so the staggered plate seams, rivets and the runs from them are generated, over the real rust.

- rusty_metal_05, Amal Kumar, CC0, https://polyhaven.com/a/rusty_metal_05: the base. Delit, a scratch mark cloned out, its blue paint turned to dull grey steel.
- rusty_metal_04, Amal Kumar, CC0, https://polyhaven.com/a/rusty_metal_04: delit, its dark flaking rust masked in.
- rust_coarse_01, Dimitrios Savva and Rico Cilliers, CC0, https://polyhaven.com/a/rust_coarse_01: high-passed, fine grain.

## concrete.jpg

- concrete_wall_006, Dario Barresi and Charlotte Baglioni, CC0, https://polyhaven.com/a/concrete_wall_006: the base, with its water marks and tie holes. Delit, mostly desaturated, taken to mid-grey; its brown kept as a faint stain.
- concrete_wall_007, Dario Barresi, Rico Cilliers and Charlotte Baglioni, CC0, https://polyhaven.com/a/concrete_wall_007: high-passed, shutter marks and patches.
- concrete_floor_worn_001, Dimitrios Savva and Rico Cilliers, CC0, https://polyhaven.com/a/concrete_floor_worn_001: high-passed, grain.
- dirty_concrete, Rob Tuytel, CC0, https://polyhaven.com/a/dirty_concrete: darkening only, blooms.

## asphalt.jpg

12 m across by 27 m along, so sources are squeezed about 2.25 along the rows. No road markings. Warps and the masks that break up the cracks are generated. Taken to nearly black.

- worn_asphalt, Amal Kumar, CC0, https://polyhaven.com/a/worn_asphalt: high-passed, aggregate, repeated 4 x 9.
- asphalt_07, Charlotte Baglioni, CC0, https://polyhaven.com/a/asphalt_07: high-passed, grain, repeated 3 x 7.
- cracked_concrete, Dimitrios Savva, CC0, https://polyhaven.com/a/cracked_concrete: crack mask, at two scales, one rotated.
- asphalt_02, Rob Tuytel, CC0, https://polyhaven.com/a/asphalt_02: crack mask, long cracks along the road.
- cracked_concrete_02, Charlotte Baglioni, CC0, https://polyhaven.com/a/cracked_concrete_02: crack mask, hairlines.

## sand.jpg

No CC0 source with clean dune ripples was found on Poly Haven, so the ripple lines and the amber colour are generated. The sources break the crests and add grain.

- aerial_beach_01, Rob Tuytel, CC0, https://polyhaven.com/a/aerial_beach_01: high-passed, its broken ripples push the lines about.
- dense_sand, Dimitrios Savva, CC0, https://polyhaven.com/a/dense_sand: high-passed, grain.

# The stair and tunnel sections

Made by `build-section-tex.py` from 1k colour maps, downsampled to 512 x 512 sRGB JPEG, all wrapped so they tile. No normal or roughness maps: `kit.material` only takes a colour texture. Licences checked 2026-11-05. Poly Haven: all CC0 (https://polyhaven.com/license). ambientCG: all CC0 (https://ambientcg.com/view?id=MetalPlates011, stated on the page's FAQ; https://docs.ambientcg.com/license/). The generated parts are ours and also CC0.

## wet_concrete.jpg (`wet_concrete`)

Rust runs are used only as shapes, in the dark; the broad wet patches are generated clouds.

- concrete_wall_006, Dario Barresi and Charlotte Baglioni, CC0, https://polyhaven.com/a/concrete_wall_006: the base, stains and tie holes.
- concrete_wall_007, Dario Barresi, Rico Cilliers and Charlotte Baglioni, CC0, https://polyhaven.com/a/concrete_wall_007: high-passed, shutter marks.
- concrete_floor_worn_001, Dimitrios Savva and Rico Cilliers, CC0, https://polyhaven.com/a/concrete_floor_worn_001: high-passed, grain.
- dirty_concrete, Rob Tuytel, CC0, https://polyhaven.com/a/dirty_concrete: dark blooms.
- MetalPlates010, 012, 013, ambientCG, CC0, https://ambientcg.com/view?id=MetalPlates010 (and 012, 013): masks, stains running down.

## slimy_concrete.jpg (`stained_concrete`)

- concrete_wall_007, as above: the base.
- concrete_wall_006, as above: high-passed, marks.
- concrete_floor_02, Rob Tuytel, CC0, https://polyhaven.com/a/concrete_floor_02: high-passed, grain.
- concrete_moss, Rob Tuytel, CC0, https://polyhaven.com/a/concrete_moss: the slime's colour.
- mossy_rock, Rob Tuytel, CC0, https://polyhaven.com/a/mossy_rock: high-passed, breaks up the slime.
- MetalPlates010, 012, 013, ambientCG, CC0, as above: masks, where the slime and the black runs sit.

## heavy_rust.jpg (`rust`)

- MetalPlates012, ambientCG, CC0, https://ambientcg.com/view?id=MetalPlates012: base, rust over bared steel, darkened.
- MetalPlates011, ambientCG, CC0, https://ambientcg.com/view?id=MetalPlates011: solid rust, masked in by generated clouds.
- rusty_metal_05, Amal Kumar, CC0, https://polyhaven.com/a/rusty_metal_05: scaling.
- rusty_metal_04, Amal Kumar, CC0, https://polyhaven.com/a/rusty_metal_04: dark flaking, as pits.
- rust_coarse_01, Dimitrios Savva and Rico Cilliers, CC0, https://polyhaven.com/a/rust_coarse_01: high-passed, grain.
- MetalPlates010, ambientCG, CC0, as above: dark runs.

## riveted_steel.jpg (`riveted_steel`)

Near-black gun-metal. Still no CC0 source with rivets, so the plates, seams and rivets are generated, over real steel.

- MetalPlates013, ambientCG, CC0, https://ambientcg.com/view?id=MetalPlates013: the surface, desaturated, darkened.
- metal_plate_02, Rob Tuytel, CC0, https://polyhaven.com/a/metal_plate_02: high-passed, scuffs.
- rusty_metal_04, Amal Kumar, CC0, as above: high-passed, fine marks.
- rust_coarse_01, as above: the colour of the rust hints. MetalPlates012, as above: where they run.

## dark_steel.jpg (`pipe_metal`)

Riveted steel's surface without the plates, for pipes and fittings. Same sources.

## paint_grey.jpg (`paint_grey`)

Old grey paint on metal.

- rusty_metal_sheet, Amal Kumar, CC0, https://polyhaven.com/a/rusty_metal_sheet: the coat and its chips, colour taken down to grey.
- green_metal_rust, Rob Tuytel, CC0, https://polyhaven.com/a/green_metal_rust: high-passed, wear.
- MetalPlates013, ambientCG, CC0, as above: mask, grime runs.
