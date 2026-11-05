# The stairwell and flooded tunnel: approved ride, sizes, assets

The target is the user's own images: `art/reference/concept-stairwell.webp` and `art/reference/concept-flooded-tunnel.webp`. Match their
materials, lighting and shapes. Don't invent a different design. Where they differ from the list below, the user's note wins: the stairwell
picture is "almost peaceful", so make it as tight and pressing as the tunnel. No real brands. The scene is drawn at 1/7 resolution, so bold
shapes and strong lighting beat fine detail: check your `-px7` still.

## The approved ride (the user's sign-off: don't add to it or change it)

Stairwell, 900 m of road: about 30 s at about 30 m/s; the boost is off for all of it, for the moving pieces:
1. Lab doors open onto the reference shot: the top of a long flight, looking down the square shaft past B4 and B5.
2. Rattling down the steps, rails both sides, red strips streaking past, big pipes close on the left.
3. At the first corner, no turn: up onto the wall past the stencilled level number, then down onto the next flight.
4. Along the outer edge of a landing, right by the rail, the open shaft beside you.
5. A flight torn away: jump the gap across the shaft, thump down on the landing below.
6. Tighter going down: pipes and beams crowd in, steam bursts across the road, red lights flash by.
7. Fog thickens, the green glow grows, and the last flight runs into black water.

Flooded tunnel, 1540 m of road: about 43 s at about 36 m/s; 2 boosts (about 150 m/s here) and 2 recharges long:
8. Hits the water, spray up both sides, in the ribbed tube with green caged lamps and thick cables. On a bend, up the curve of the wall and back.
9. The rusted round bulkhead, half open, red light behind: through the gap, through the red tank room, on to the servers.

Walls are short moments at corners, not the route.

## Fixed sizes (metres, Blender z up; the road's direction is +X)

- Road/flight width 11.8 (kit.ROAD_W), rails at y = +/-6.1, rail height 1.1.
- Steps: 1.2 tread, 0.5 rise (22.6 degrees). `stair_flight_12` is 10 steps: 12 m along, 5 m down.
- Landing 16 x 16. Central void 12 x 12. Outer wall's inner face 22 m from the shaft's centre.
- Lowest clearance over the road 5.5 (beams), bike and rider stand 1.6.
- Tube: inner radius 9, centre 5.5 above the deck, so its floor's 3.5 under the deck; water surface at z +0.35 over the deck. Rings every 8.
- Bulkhead opening diameter 17; door 17.6 across, 1.6 thick; the gap it leaves is 14 wide. Red room 34 wide, 70 long, 15 high.

## The contract (`art/core/assets/_common.py` and `_template.py` do it for you)

- One script per asset: `art/core/assets/<name>.py`, copied from `_template.py`, exports `art/out/assets/<name>.glb` and stills to
  `art/renders/assets/<name>.png` and `-px7.png`. Run: `/opt/homebrew/bin/blender --background --factory-startup --python art/core/assets/<name>.py`
- Origin and axes as the row says; true size; within the triangle budget (`A.finish` enforces it).
- Materials only from `assets/_mats.py` (`_mats.mats(kit)`), by name. Don't make your own. If you need one more, ask the surfaces agent's file by adding a
  line there, and say so in your report.
- Bake light with `kit.bake_light`: dim, red and green from where the section's lamps would be, as in the images.
- Blender headless only, from scripts: never the Blender MCP. Touch only your own assets' scripts and outputs. Don't commit. Don't touch the site or the current city5 build.

## Assets

| Group | Name | What, and size | Origin | Tris |
|---|---|---|---|---|
| Stair structure | stair_flight_12 | 10 steps, 11.8 wide, side stringers, wet tops, worn edges | top step, road centre | 500 |
| | stair_landing | 16 x 16 slab, drain, hazard-paint edge | top centre | 250 |
| | stair_wall_panel | 16 wide x 16 high: stained concrete panel, ribs, conduit grooves | base centre, faces +Y | 300 |
| | stair_wall_ramp | Banked curve from a landing's floor up onto a wall, 90 degrees over, 24 long | start, road centre | 800 |
| | stair_beam_low | Low concrete/steel beam across the road, 14 long, 1.4 deep | centre | 150 |
| | stair_flight_torn | A flight's broken end: snapped slab, rebar, hanging rail | top step | 900 |
| Rails and hazards | rail_12 | 12 m rail with posts and kick plate, follows the 22.6 degree slope | top end | 200 |
| | rail_flat_16 | 16 m level rail, for landing edges | end | 160 |
| | rail_bent | A rail wrecked and bent out over the shaft | end | 300 |
| | hazard_trim | Yellow-black edge strip and floor grate, 12 long | end | 80 |
| | wall_ladder | Rung ladder with cage, 12 high | base | 200 |
| Pipes and cables | pipe_big_12 | 1.3 diameter run with flanges, 12 long, along +X | end, centre of pipe | 350 |
| | pipe_elbow | Same bore, 90 degree elbow | one end | 300 |
| | pipe_cluster_12 | Three or four mixed pipes on brackets, 12 long, as on the image's left | end, wall side | 700 |
| | pipe_valve | Big handwheel valve in a pipe | centre | 400 |
| | pipe_broken | Pipe sheared open, for steam, jagged | end | 350 |
| | cable_tray_12 | Tray on brackets with bundled cables, 12 long | end | 350 |
| | cable_bundle_12 | Thick black bundle with clamps, 12 long | end | 300 |
| | cable_bundle_arc | The same curving along the tube's wall (radius 8.6, 8 long) | end | 350 |
| Lights | light_red_strip | The images' red wall strip, 2.8 x 0.25, housing and glow face | back centre | 60 |
| | light_green_cage | The tunnel's caged green lamp, 1.3 wide | back centre | 120 |
| | light_white_cage | The tunnel's slanted white work light with cage, 2.4 long | back centre | 150 |
| | light_ceiling_tube | Long fluorescent batten, 3 long, as at the stair's top | top centre | 100 |
| | light_beacon_red | Red alarm beacon, 0.5 | base | 60 |
| Wall dressing | panel_green_data | The images' green data window, 2 x 2.6, deep frame, `screen` face | back centre | 120 |
| | wall_fan | Wall vent fan, 4 across, in a housing | back centre | 400 |
| | door_steel | Heavy steel door and frame, 4 x 6 | base centre | 250 |
| | stencil_levels | Plates with sprayed B4 to B12 and a slash, large (3 m), one object per level name, named stencil_B4 and so on | back centre | 40 each |
| | junction_box | Grey wall box with conduit stubs | back centre | 150 |
| Things that move | debris_set | 6 falling concrete/steel chunks, as separate objects | each own centre | 500 total |
| | flight_collapse | A flight breaking away and falling, as a glTF animation, 2 s, to be scrubbed by the ride's distance | top step | 1800 |
| | beam_swing | A hanging beam swinging down across the road, animation, 1.5 s | pivot | 400 |
| | shutter_slam | Steel shutter dropping part way, animation, 0.5 s | top centre | 300 |
| Tunnel structure | tube_ring_8 | 8 m of tube, radius 9: stained concrete with moss, one steel rib, cross-tie rods | centre of the deck, ring's back | 900 |
| | tube_ring_riveted | The same, riveted steel plates | same | 1100 |
| | tube_walkway_8 | Side walkway with rail, 8 long, as in the image's lower left | end | 200 |
| | tube_side_duct | A dark side duct mouth with louvres | back centre | 500 |
| | tube_cross_grate | Overhead grating and ladder from the crown | top centre | 400 |
| Bulkhead | bulkhead_frame | Hero piece: huge round riveted frame round the opening, in the tube's end wall | centre of the opening | 5000 |
| | bulkhead_door | Hero piece: round rusted door with ribs and a brass wheel, 17.6 across, hinged at its origin | hinge | 5000 |
| | red_room_shell | Room behind: walkway, rails, gantries, red-lit, 34 x 70 x 15 | floor centre, near end | 3000 |
| | red_tank | Glowing red cylinder tank with base and cap, radius 3.3, 10 high | base centre | 500 |

Found, not modelled (CC0 only: Poly Haven, ambientCG, Freesound CC0, Kenney; record each in a LICENSES.md):

| Group | What | Where |
|---|---|---|
| Surfaces | Wet stained concrete, slimy concrete, heavy rust, riveted steel: 512 x 512, tiling, in the manner of `art/core/tex`; points `assets/_mats.py` at them | `art/core/tex/` |
| Water and effects | Water normal map; flipbook sprite sheets for spray, steam burst, sparks, drips | `art/core/fx/` |
| Sound | Rushing water, splash, steam burst, metal impacts, concrete collapse, stair rattle loop: Ogg and m4a, short and trimmed | `art/audio/sections/` |
