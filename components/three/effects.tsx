'use client';

import { useFrame } from '@react-three/fiber';
import { Bloom, DepthOfField, EffectComposer, GodRays, Noise, SMAA, Vignette } from '@react-three/postprocessing';
import {
  BlendFunction,
  type BloomEffect,
  type DepthOfFieldEffect,
  type Effect,
  type GodRaysEffect,
  type NoiseEffect,
  type SMAAEffect,
  type VignetteEffect,
} from 'postprocessing';
import { useRef } from 'react';
import { type Mesh, ShaderChunk, type Sphere, Vector3 } from 'three';
import { devFlag, journey, landingAt, smoothstep } from '@/lib/journey';
import { look } from '@/lib/look';
import { RHYTHM, rhythm } from '@/lib/rhythm';
import { CRUISE, featureHere, ride, washCover } from '@/lib/ride';
import { Grade, type GradeEffect } from './grade';
import { LiquidSweep, type LiquidSweepEffect } from './liquid-sweep';
import { NearBlur, type NearBlurEffect } from './near-blur';
import { PixelSweep, type PixelSweepEffect } from './pixel-sweep';
import { bloomAt, SUN_POSITION } from './sky';
import { SpeedBlur, type SpeedBlurEffect } from './speed-blur';

const sunOnScreen = new Vector3();

// Every built-in material ends with this chunk: keep its output finite and in range. The effects render to a
// half-float buffer, and one Inf or NaN pixel (a sun glint on glossy clay can overflow it) gets smeared by the bloom
// into a black speck, or across the whole screen.
if (!ShaderChunk.dithering_fragment.includes('isnan')) {
  ShaderChunk.dithering_fragment += `
if (any(isnan(gl_FragColor)) || any(isinf(gl_FragColor))) gl_FragColor = vec4(0.0);
gl_FragColor.rgb = min(gl_FragColor.rgb, vec3(16.0));`;
}

/**
 * The finish: bloom on anything brighter than white (the sun, glints and white water), light rays from the sun, and
 * a little vignette and grain once the journey is under way. The hero has none of it, so it matches the blog.
 */
export function Effects({ sun, pixel }: { sun: Mesh | null; pixel: number }) {
  const vignette = useRef<VignetteEffect>(null);
  const grain = useRef<NoiseEffect>(null);
  const grade = useRef<GradeEffect>(null);
  const nearBlur = useRef<NearBlurEffect>(null);
  const rays = useRef<GodRaysEffect>(null);
  const focus = useRef<DepthOfFieldEffect>(null);
  const bloomFx = useRef<BloomEffect>(null);
  const sweep = useRef<PixelSweepEffect>(null);
  const liquid = useRef<LiquidSweepEffect>(null);
  const speedBlur = useRef<SpeedBlurEffect>(null);
  const smaa = useRef<SMAAEffect>(null);
  // Effects only needed some of the time are switched out of the composite while they're idle (the shader recompiles,
  // once, as each changes) and their own off-screen work is skipped: the lens blurs belong to the still landing shot,
  // the edge smoothing to full-resolution rendering, the pixel wipe to the pre-roll.
  const gates = useRef(new Map<Effect, boolean>());
  const gate = (effect: Effect | null, on: boolean) => {
    if (!effect) return;
    if (!gates.current.has(effect)) {
      const update = effect.update.bind(effect);
      effect.update = (renderer, input, delta) => {
        if (gates.current.get(effect)) update(renderer, input, delta);
      };
    }
    if (gates.current.get(effect) === on) return;
    gates.current.set(effect, on);
    effect.blendMode.blendFunction = on ? BlendFunction.NORMAL : BlendFunction.SKIP;
  };

  useFrame((state) => {
    const underway = smoothstep(10, 120, journey.frame);
    const bloom = bloomAt(journey.frame);
    if (vignette.current) vignette.current.darkness = 0.18 * underway + 0.12 * bloom;
    if (grain.current) grain.current.blendMode.opacity.value = 0.05 * underway;
    // The extra glow is for the still landing shot only: on the approach, right up against the white fall, it would
    // blow out to white.
    const arrived = smoothstep(720, 765, journey.frame);
    // Some of the landing's glow on the way down too, so the sunlit water and rock shine rather than sit flat.
    const glow = Math.max(0.45 * bloom * (1 - smoothstep(560, 700, journey.frame)), arrived);
    if (grade.current) {
      // The warm, saturated grade comes in with the real sky as the camera leaves the hero, not only at the landing.
      grade.current.weight = Math.max(bloom, landingAt(journey.frame));
      // (Brighter on the way down: the landing's exposure is set for its stronger low sun.)
      grade.current.exposure = 0.82 + 0.08 * (1 - landingAt(journey.frame)) + look.exposure * look.day;
      grade.current.setDusk(look.day, look.tone, look.saturation);
      grade.current.glow = 0.55 * glow;
      // Where the sun is on screen, for its starburst (only at the landing, and not when it's behind the camera).
      // (From the sun disc itself, the centre of its geometry: Blender's mesh isn't centred on its origin.)
      if (sun) {
        if (!sun.geometry.boundingSphere) sun.geometry.computeBoundingSphere();
        sunOnScreen.copy((sun.geometry.boundingSphere as Sphere).center).applyMatrix4(sun.matrixWorld);
      } else sunOnScreen.copy(SUN_POSITION).add(state.camera.position);
      // (The camera has moved this frame but its matrices only update when it renders.)
      state.camera.updateMatrixWorld();
      sunOnScreen.project(state.camera);
      const facing = sunOnScreen.z < 1 ? 1 : 0;
      // (No sun at night: its lens starburst stays off.)
      grade.current.setSun(sunOnScreen.x * 0.5 + 0.5, sunOnScreen.y * 0.5 + 0.5, 0 * facing * arrived, state.size.width / state.size.height);
    }
    // Gentler rays at the landing: full strength they wash the sky's clouds out round the sun.
    // The landing's lens: sharp from the frog out past the lilies (the focus is centred mid-way, its range wide, since
    // the blur is symmetric about it), the far valley, mountains and cliffs going soft (the reference's depth of field). Off everywhere else.
    // The blurs are measured in buffer pixels: at pixel mode's low resolution each covers far more of the screen, so
    // they're scaled down to look the same.
    const scale = Math.min(1, state.gl.getPixelRatio() / 1.75);
    // (The still landing shot only: not on the way down, nor once on the bike.)
    const still = landingAt(journey.frame) * (1 - ride.mount);
    if (focus.current) focus.current.bokehScale = 1.8 * still * Math.max(scale, 0.35);
    gate(focus.current, still > 0.01);
    gate(nearBlur.current, still > 0.01);
    gate(smaa.current, state.gl.getPixelRatio() >= 1);
    gate(sweep.current, !pixel || journey.sweep < 1);
    if (sweep.current) sweep.current.set(pixel ? journey.sweep : 0, pixel * state.gl.getPixelRatio());
    // Motion blur from the bike's speed, only from the rider's seat (and off in a gate when still, costing nothing).
    // (Surging, the blur deepens and the iridescent sheen comes in round the edges.)
    // (Launched from the slingshot, it streaks harder still and flames lick in round the view.)
    const surge = ride.mount * ride.drive.surge;
    const fire = ride.mount * ride.drive.fire;
    // (In the hive the veins show the heart's beat faintly even unpumped, so the rhythm's there to tap to.)
    const hive = ride.mount * (featureHere() === 'heartbeat' ? 1 : 0);
    const veins = hive * (0.18 + 0.82 * Math.max(ride.drive.pump, rhythm.active ? (0.5 * rhythm.landed) / RHYTHM.count : 0));
    const blur = devFlag('noblur') ? 0 : ride.mount * Math.min(1, ride.drive.speed / CRUISE) ** 1.5 * (1 + 0.8 * surge + 0.8 * fire + 0.6 * ride.drive.pump);
    if (speedBlur.current) speedBlur.current.set(Math.min(blur, 2.4), surge, fire, veins, ride.drive.beat);
    gate(speedBlur.current, blur > 0.002 || surge > 0.002 || fire > 0.002 || veins > 0.002);
    if (liquid.current) {
      const { cover, leaving } = washCover();
      liquid.current.set(cover, leaving);
    }
    // (No edge smoothing once it's pixels: they should stay crisp.)
    if (smaa.current) smaa.current.blendMode.opacity.value = state.gl.getPixelRatio() < 1 ? 0 : 1;
    // A livelier bloom at the landing: more of the bright scene glows (glints, lit rims, the fall, the mist).
    if (bloomFx.current) {
      bloomFx.current.luminanceMaterial.threshold = 1.1 - 0.2 * arrived;
      bloomFx.current.intensity = 0.55 + 0.25 * arrived;
    }
    if (rays.current) rays.current.godRaysMaterial.weight = 0.6 * (1 - 0.85 * landingAt(journey.frame));
    // The shallow focus is the landing's still shot.
    if (nearBlur.current) {
      nearBlur.current.weight = still;
      nearBlur.current.radius = 14 * Math.max(scale, 0.3);
    }
  });

  // No multisampling (4x MSAA on every half-float buffer was the single biggest cost); SMAA smooths edges instead.
  return (
    <EffectComposer multisampling={0} autoClear={false}>
      {!devFlag('nodof') && <DepthOfField ref={focus} focusDistance={7} focusRange={24} bokehScale={0} />}
      <NearBlur ref={nearBlur} />
      <Bloom ref={bloomFx} mipmapBlur luminanceThreshold={1.1} luminanceSmoothing={0.25} intensity={0.55} radius={0.7} />
      {sun && !devFlag('norays') && <GodRays ref={rays} sun={sun} samples={60} density={0.97} decay={0.95} weight={0.6} exposure={0.62} clampMax={1} blur />}
      <Grade ref={grade} />
      <Vignette ref={vignette} offset={0.35} darkness={0} />
      <Noise ref={grain} premultiply blendFunction={BlendFunction.SOFT_LIGHT} opacity={0} />
      <SMAA ref={smaa} />
      <SpeedBlur ref={speedBlur} />
      <PixelSweep ref={sweep} />
      <LiquidSweep ref={liquid} />
    </EffectComposer>
  );
}
