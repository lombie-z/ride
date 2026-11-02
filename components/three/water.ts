import { Color, DoubleSide, FrontSide, type Material, MeshPhysicalMaterial } from 'three';

// The planter's liquid, on the water modelled in Blender (art/build-spill.py water_materials): black and oily, a dead
// black core lifting to a faint gunmetal sheen at the edges by facing ratio, glossy, all but opaque. Falling water carries per-vertex '_flow' (0 still, 1 falling), '_foam' (white
// water) and '_fade' (the streams crossfading into the big fall), and its UV v runs along it in metres (glTF stores
// 1 - v), so streaks can flow down it.

const DEEP = new Color().setRGB(0.003, 0.003, 0.004);
const MID = new Color().setRGB(0.012, 0.014, 0.016);
const PALE = new Color().setRGB(0.06, 0.068, 0.072);
// Where water would whiten (streaks, churn, rings), the oil only catches a sheen.
const SHEEN = /* glsl */ 'vec3(0.1, 0.11, 0.11)';

const NOISE = /* glsl */ `
float waterHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float waterNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(waterHash(i), waterHash(i + vec2(1, 0)), u.x), mix(waterHash(i + vec2(0, 1)), waterHash(i + vec2(1, 1)), u.x), u.y);
}
`;

export type WaterKind = 'falling' | 'still' | 'pool';

/** Shared clock for every water material; advance it once a frame. */
export const waterTime = { value: 0 };
/** How far into the landing the camera is (lib/journey.ts landingAt): the streams there give way to the strand curtain. */
export const waterLanding = { value: 0 };
/** How far the planter's streams have faded, with the planter itself (lib/journey.ts toyPresence). */
export const waterFromSky = { value: 0 };
/** 1 once the world below is drawn (lib/journey.ts belowVisible): the streams then end on the rock ledge under the planter. */
export const waterLedge = { value: 0 };
// The ledge's top (art/build-landing.py LEDGE_TOP; three's y).
const LEDGE_TOP = -0.7;

export function waterMaterial(kind: WaterKind): Material {
  // The pool lies flat under the low sun: a softer sheen there, or the sun's reflection blooms into a glare.
  // Nothing smoother than ~0.1 roughness: a near-mirror highlight overflows the effects' half-float buffer (Inf), and
  // bloom turns that into black specks.
  const pool = kind === 'pool';
  const material = new MeshPhysicalMaterial({
    // (Falling water is aerated, a froth of white rather than a mirror: little gloss.)
    roughness: pool ? 0.18 : kind === 'falling' ? 0.16 : 0.1,
    clearcoat: pool ? 0.35 : kind === 'falling' ? 0.8 : 1,
    clearcoatRoughness: pool ? 0.12 : 0.1,
    specularIntensity: pool ? 0.45 : 1,
    transparent: true,
    depthWrite: kind !== 'falling',
    side: kind === 'falling' ? DoubleSide : FrontSide,
  });
  material.defines = { [kind.toUpperCase()]: '' };
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uTime = waterTime;
    shader.uniforms.uLanding = waterLanding;
    shader.uniforms.uFromSky = waterFromSky;
    shader.uniforms.uLedge = waterLedge;
    shader.uniforms.uDeep = { value: DEEP };
    shader.uniforms.uMid = { value: MID };
    shader.uniforms.uPale = { value: PALE };
    shader.vertexShader = shader.vertexShader
      .replace(
        '#include <common>',
        `#include <common>
#ifdef FALLING
attribute float _flow;
attribute float _foam;
attribute float _fade;
#endif
varying float vFlow;
varying float vFoam;
varying float vFade;
varying vec2 vFlowUv;
varying vec3 vWorld;`
      )
      .replace(
        '#include <begin_vertex>',
        `#include <begin_vertex>
#ifdef FALLING
vFlow = _flow; vFoam = _foam; vFade = _fade;
#else
vFlow = 0.0; vFoam = 0.0; vFade = 1.0;
#endif
vFlowUv = uv;
vWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;`
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
uniform float uTime;
uniform float uLanding;
uniform float uFromSky;
uniform float uLedge;
uniform vec3 uDeep;
uniform vec3 uMid;
uniform vec3 uPale;
varying float vFlow;
varying float vFoam;
varying float vFade;
varying vec2 vFlowUv;
varying vec3 vWorld;
${NOISE}`
      )
      .replace(
        '#include <normal_fragment_maps>',
        `#include <normal_fragment_maps>
{
  float facing = clamp(abs(dot(normal, normalize(vViewPosition))), 0.0, 1.0);
  float edge = 1.0 - facing;
  // Still water keeps the deep blue nearly to the rim; falling water pales sooner.
  float midAt = mix(0.9, 0.55, vFlow);
  vec3 water = edge < midAt ? mix(uDeep, uMid, edge / midAt) : mix(uMid, uPale, (edge - midAt) / (1.0 - midAt));
  float white = 0.0;
#ifdef FALLING
  // Streaks flowing down the fall (metres along it = 1 - v), stretched lengthwise.
  float along = 1.0 - vFlowUv.y;
  float streak = waterNoise(vec2(vFlowUv.x * 14.0, (along - uTime * 1.6) * 1.1));
  streak = smoothstep(0.6, 0.78, streak) * 0.65 * vFlow;
  float churn = smoothstep(0.35, 0.65, waterNoise(vec2(vFlowUv.x * 22.0, (along - uTime * 1.2) * 5.0)));
  white = max(streak, vFoam * churn);
  // Real water from the planter's lip down: white, aerated, streaming.
  float aerated = 0.9 * vFlow;
  float fine = waterNoise(vec2(vFlowUv.x * 60.0, (along - uTime * 2.6) * 0.8)) * 0.6 + waterNoise(vec2(vFlowUv.x * 170.0, (along - uTime * 3.4) * 2.0)) * 0.4;
  float streaks = smoothstep(0.32, 0.68, fine);
  // (Oil pours smooth: the streaks are only a faint ripple in its sheen.)
  white = max(white, aerated * streaks) * 0.3;
  // Between the streaks the curtain stays black.
#endif
#ifdef POOL
  // Rings spreading out from where the big fall lands.
  float d = length(vWorld.xz);
  float ring = smoothstep(0.82, 1.0, sin(d * 16.0 - uTime * 3.2)) * exp(-d * 1.1) * step(0.42, d);
  white = ring * 0.55;
#endif
  diffuseColor.rgb = mix(water, ${SHEEN}, white);
  diffuseColor.a = mix(0.97, 1.0, white) * vFade;
#ifdef FALLING
  // Nearly opaque in the streaks, a little thinner between them. (Not thinned at the landing: by then the oil ropes,
  // components/three/fall-streaks.tsx, carry the fall and the streams have gone with the planter.)
  diffuseColor.a *= mix(1.0, mix(0.8, 0.95, streaks), aerated);
  // The streams land on the ledge (nothing of them below its top), and fade with the planter, a little behind it: the
  // oil ropes (components/three/fall-streaks.tsx) have reached up out of the sky in their place by then.
  if (uLedge > 0.5 && vWorld.y < ${LEDGE_TOP.toFixed(2)}) discard;
  diffuseColor.a *= 1.0 - smoothstep(0.4, 1.0, uFromSky);
  // Ragged, broken edges where the curtain is seen edge-on: it frays into separate streams rather than ending in a
  // clean silhouette.
  float rim = 1.0 - clamp(abs(dot(normal, normalize(vViewPosition))), 0.0, 1.0);
  float fray = waterNoise(vec2(vFlowUv.x * 60.0, (along - uTime * 2.2) * 0.8));
  diffuseColor.a *= 1.0 - smoothstep(0.55, 0.9, rim) * smoothstep(0.35, 0.65, fray) * aerated;
#endif
}`
      );
  };
  material.customProgramCacheKey = () => `water-${kind}`;
  return material;
}
