"""The new sections' shared materials, by name: one material however many assets use it, so a landing asset can't drift from
the rest. Owned by the surfaces agent (art/core/ASSETS.md), who points these at the final textures; everyone else only calls it.

    import _mats
    m = _mats.mats(kit)
    me = kit.mesh_from('stair_flight_12', bm, [m['wet_concrete'], m['rust']])
"""


def mats(kit):
    return {
        'wet_concrete': kit.material('City5WetConcrete', (0.27, 0.27, 0.24), 0.55, tex='wet_concrete', spec=0.6),
        'stained_concrete': kit.material('City5StainedConcrete', (0.2, 0.21, 0.17), 0.7, tex='slimy_concrete', spec=0.4),
        'rust': kit.material('City5SectionRust', (0.3, 0.17, 0.09), 0.62, 0.45, tex='heavy_rust'),
        'riveted_steel': kit.material('City5RivetedSteel', (0.17, 0.17, 0.16), 0.48, 0.7, tex='riveted_steel'),
        'pipe_metal': kit.material('City5PipeMetal', (0.11, 0.1, 0.09), 0.32, 0.85, tex='dark_steel'),
        'cable': kit.MAT['cable'],
        'dark': kit.MAT['dark'],
        'hazard': kit.MAT['hazard'],
        'red': kit.MAT['red'],
        'green': kit.MAT['led'],
        'white': kit.MAT['light'],
        'screen': kit.MAT['screen'],
        # Wall dressing: the junction box's and fan guard's pale paint; the sprayed level codes' alpha (only once stencil_levels.py has registered its texture).
        'paint_grey': kit.material('City5PaintGrey', (0.74, 0.75, 0.71), 0.5, 0.1, tex='paint_grey'),
        'stencil': kit.material('City5Stencil', (0.8, 0.77, 0.7), 0.85, tex='stencil', alpha_tex=True, spec=0.2) if 'stencil' in kit._gen else None,
        # The lamps' glow faces, under their hot cores: the saturated red and green round the images' pale centres. (Names end in Red/Led so the site lets them past white.)
        'lamp_red': kit.material('City5LampGlowRed', (0.6, 0.012, 0.01), 0.4, vcol=False, emission=(1.0, 0.018, 0.014), strength=1.0),
        'lamp_green': kit.material('City5LampGlowLed', (0.06, 0.5, 0.03), 0.4, vcol=False, emission=(0.09, 0.7, 0.035), strength=1.0),
        'lamp_green_hot': kit.material('City5LampHotLed', (0.4, 0.9, 0.2), 0.4, vcol=False, emission=(0.36, 1.0, 0.16), strength=1.8),
        'lamp_red_hot': kit.material('City5LampHotRed', (1.0, 0.25, 0.2), 0.4, vcol=False, emission=(1.0, 0.055, 0.047), strength=4.7),
        # The cages' wires, catching their lamps.
        'lamp_wire': kit.material('City5LampWire', (0.5, 0.42, 0.3), 0.5, vcol=False, emission=(0.55, 0.42, 0.28), strength=1.0),
        # The bulkhead group's light, painted in (only once _bulkhead.py has registered its textures): door, frame, the lit-per-vertex ramp, the tank's far wall and glass.
        **({
            'bulkhead_door': kit.material('City5BulkheadDoor', (1, 1, 1), 0.6, 0.25, tex='bulkhead_door', emission=(1, 1, 1), strength=1.0, emit_tex=True, spec=0.3),
            'bulkhead_frame': kit.material('City5BulkheadFrame', (1, 1, 1), 0.65, 0.2, tex='bulkhead_frame', emission=(1, 1, 1), strength=1.0, emit_tex=True, spec=0.3),
            'bulkhead_ramp': kit.material('City5BulkheadRamp', (1, 1, 1), 0.85, 0.0, vcol=False, tex='bulkhead_ramp', emission=(1, 1, 1), strength=1.0, emit_tex=True, spec=0.1),
            'bulkhead_tank': kit.material('City5TankLinerRed', (0.3, 0.02, 0.01), 0.5, vcol=False, tex='bulkhead_tank', emission=(1, 1, 1), strength=1.5, emit_tex=True),
            'red_tank_glass': kit.material('City5RedTankGlass', (1.0, 0.45, 0.4), 0.06, 0.1, vcol=False, alpha=0.1, spec=0.8),
            # The door's four win lamps, one material each so the site can switch each alone, in the brass look's colours (lib/doors.ts: dark #3c2412, lit #ff5a2a), off as exported.
            **{f'bulkhead_lamp_{i}': kit.material(f'City5BulkheadLamp{i}Red', (0.045, 0.018, 0.006), 0.3, vcol=False, emission=(1.0, 0.102, 0.023), strength=0.012) for i in (1, 2, 3, 4)},
        } if 'bulkhead_door' in kit._gen else {}),
    }
