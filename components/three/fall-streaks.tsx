'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import {
  Color,
  DoubleSide,
  Float32BufferAttribute,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  type Mesh,
  type Object3D,
  ShaderMaterial,
  UniformsLib,
  UniformsUtils,
  Vector3,
} from 'three';
import { belowVisible, devFlag, journey, smoothstep } from '@/lib/journey';
import { ride } from '@/lib/ride';
import { waterFromSky, waterJoin } from './water';

// The planter's oil carried on down: the streams modelled in Blender (the Fall.* meshes, components/three/water.ts)
// leave the rim as narrow ropes and then flare out into a wide bell as they braid (down to y -4.7); below the hero,
// these ropes take over from them just under the rim, before the flare (water.ts cuts the streams off there, JOIN_Y),
// and pour on past the freeway into the abyss among the towers, to the city's floor. Viscous oil doesn't break up into spray as water does: it
// falls in long, unbroken, glossy ropes, black, catching the city's green light along their edges. Each rope is a strip
// turned to face the camera about its own (vertical) axis and shaded as a wet cylinder; bulges travel down it with the
// oil, stretching as it speeds up. Once the planter has gone into the haze above (lib/journey.ts toyPresence), the
// ropes reach on up out of the sky too, in place of the streams.

/** The city's floor, far below the freeway deck (art/build-city.py; three's y). */
export const OIL_FLOOR = -80;
// Where the ropes reach up to once they pour out of the sky, and the haze they fade into on the way.
const SKY_TOP = 46;
const HAZE = [16, 42];
const GRAVITY = 9.8;
/** Where the ropes take over from the streams (three y), still narrow under the rim, above their flare. */
export const JOIN_Y = -1.7;

/** Each of the planter's streams where the ropes take over (JOIN_Y): its middle, its width, and points across it. */
export function streamEnds(scene: Object3D) {
  const ends: { centre: Vector3; width: number; points: Vector3[] }[] = [];
  scene.updateMatrixWorld(true);
  scene.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh || !mesh.name.startsWith('Fall') || mesh.name.startsWith('FallMain')) return;
    const pos = mesh.geometry.getAttribute('position');
    const points: Vector3[] = [];
    for (let i = 0; i < pos.count; i++) {
      const p = new Vector3().fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
      if (Math.abs(p.y - JOIN_Y) < 0.12) points.push(p);
    }
    if (!points.length) return;
    const centre = points.reduce((sum, p) => sum.add(p), new Vector3()).divideScalar(points.length);
    const extent = (axis: 'x' | 'z') => Math.max(...points.map((p) => p[axis])) - Math.min(...points.map((p) => p[axis]));
    // (About as wide as the stream there, seen from any side.)
    const width = Math.min(0.3, Math.max(0.1, 0.8 * ((extent('x') + extent('z')) / 2)));
    ends.push({ centre: centre.setY(JOIN_Y), width, points });
  });
  return ends;
}

const vertexShader = /* glsl */ `
#include <fog_pars_vertex>
uniform float uTime;
uniform float uResX;
uniform float uMinPx;
attribute vec3 aRoot;
attribute float aWidth;
attribute float aSeed;
attribute float aV0;
varying vec3 vWorld;
varying vec3 vRight;
varying float vU;
varying float vCover;
varying float vSlope;
varying float vSeed;
varying float vRootY;
varying float vLaunch;
void main() {
  float y = mix(${SKY_TOP.toFixed(1)}, ${OIL_FLOOR.toFixed(1)}, position.y);
  // Metres fallen since the stream's end, and the speed it's reached (it left there at aV0).
  float fallen = aRoot.y - y;
  float d = max(fallen, 0.0);
  float v = sqrt(aV0 * aV0 + ${(2 * GRAVITY).toFixed(1)} * d);
  // When the oil now here left the stream's end (above it, it's on its way down from the sky at aV0): bulges in the
  // rope are carried with the oil, so they race down and stretch out as it speeds up.
  float launch = uTime - (fallen > 0.0 ? (v - aV0) / ${GRAVITY.toFixed(1)} : fallen / aV0);
  float bulge = sin(launch * 5.3 + aSeed * 40.0) * 0.6 + sin(launch * 11.7 + aSeed * 13.0) * 0.4;
  // The ropes spread apart as they fall, out from under the planter and wandering in the updraft from the city (none
  // where they leave the streams), leaning away from the road that runs past them on the landing's right (+z;
  // art/build-city.py), never toward it.
  float drift = d / (d + 22.0);
  vec3 c = vec3(aRoot.x, y, aRoot.z);
  c.xz += normalize(aRoot.xz + vec2(1e-4)) * vec2(1.4, 0.5) * drift;
  c.x += (sin(y * 0.05 + aSeed * 6.28 + uTime * 0.22) * 0.8 + sin(y * 0.17 + aSeed * 17.0) * 0.2) * drift;
  c.z += (cos(y * 0.04 + aSeed * 4.1 + uTime * 0.18) * 0.6 - 0.4) * drift;
  // Necking as it speeds up (a falling column thins), with the bulges riding down it (none at the join, where it
  // matches the stream it carries on).
  float w = aWidth * mix(1.0, 0.45, d / (d + 12.0)) * (1.0 + 0.18 * bulge * smoothstep(0.5, 4.0, d));
  // Turned to face the camera about the vertical; never thinner than about a pixel, or far off it would flicker
  // in and out (thinner ropes are drawn at the minimum width and fainter instead).
  vec3 toCam = cameraPosition - c;
  vec3 right = normalize(vec3(toCam.z, 0.0, -toCam.x) + vec3(1e-5, 0.0, 0.0));
  vec4 clip = projectionMatrix * viewMatrix * vec4(c, 1.0);
  float pixel = clip.w * 2.0 / (projectionMatrix[0][0] * uResX);
  float drawn = max(w, uMinPx * pixel);
  vCover = w / drawn;
  vec3 p = c + right * position.x * 0.5 * drawn;
  vec4 mvPosition = viewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  vWorld = p;
  vRight = right;
  vU = position.x;
  // The bulges' slope tilts the surface up and down, so its sheen flickers down the rope.
  vSlope = (cos(launch * 5.3 + aSeed * 40.0) * 0.6 + cos(launch * 11.7 + aSeed * 13.0) * 0.4) * 0.35;
  vSeed = aSeed;
  vRootY = aRoot.y;
  vLaunch = launch;
  #include <fog_vertex>
}`;

const fragmentShader = /* glsl */ `
#include <fog_pars_fragment>
uniform float uIn;
uniform float uFromSky;
uniform vec3 uBase;
uniform vec3 uZenith;
uniform vec3 uHorizon;
uniform vec3 uGlow;
uniform vec3 uLight;
uniform vec3 uKeyDir;
uniform vec3 uRimDir;
varying vec3 vWorld;
varying vec3 vRight;
varying float vU;
varying float vCover;
varying float vSlope;
varying float vSeed;
varying float vRootY;
varying float vLaunch;
float oilHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  // A cylinder: the normal swings round from the camera's side to the rope's edges, tilted by the bulges.
  float u = clamp(vU, -1.0, 1.0);
  vec3 toward = vec3(-vRight.z, 0.0, vRight.x);
  vec3 n = normalize(vRight * u + toward * sqrt(max(1.0 - u * u, 0.0)) + vec3(0.0, vSlope, 0.0));
  vec3 view = normalize(cameraPosition - vWorld);
  float facing = max(dot(n, view), 0.0);
  float fresnel = 0.04 + 0.96 * pow(1.0 - facing, 5.0);
  // What the oil mirrors: the green-black night above, the haze at the horizon, the city's glow below, and the
  // towers' lit windows as specks sliding along it.
  vec3 r = reflect(-view, n);
  vec3 env = r.y > 0.0 ? mix(uHorizon, uZenith, smoothstep(0.0, 0.55, r.y)) : mix(uHorizon, uGlow, smoothstep(0.0, 0.35, -r.y));
  vec2 cell = floor(vec2(atan(r.z, r.x) * 30.0, r.y * 26.0 + vLaunch * 2.0));
  float window = step(0.93, oilHash(cell + floor(vSeed * 50.0))) * (1.0 - smoothstep(0.05, 0.45, abs(r.y)));
  env += uLight * window * 0.4;
  vec3 c = uBase + env * fresnel;
  // Glints: the city's light caught in the curve of the rope.
  vec3 h = normalize(uKeyDir + view);
  c += uLight * pow(max(dot(n, h), 0.0), 140.0) * 0.32;
  vec3 hr = normalize(uRimDir + view);
  c += uLight * pow(max(dot(n, hr), 0.0), 60.0) * 0.12;
  // Soft edges (a pixel or so); thinner than a pixel, fainter.
  float a = (1.0 - smoothstep(0.6, 1.0, abs(vU))) * mix(vCover, 1.0, 0.25) * uIn;
  // Joining the streams: nothing above their ends while the planter's there; once it's gone, the ropes reach on up
  // into the haze in its place.
  float above = smoothstep(vRootY - 0.35, vRootY + 0.15, vWorld.y);
  a *= mix(1.0, uFromSky, above);
  a *= 1.0 - smoothstep(${HAZE[0].toFixed(1)}, ${HAZE[1].toFixed(1)}, vWorld.y);
  a *= smoothstep(${OIL_FLOOR.toFixed(1)}, ${(OIL_FLOOR + 3).toFixed(1)}, vWorld.y);
  if (a < 0.003) discard;
  gl_FragColor = vec4(c, a);
  #include <colorspace_fragment>
  #include <fog_fragment>
}`;

// Segments along each rope (top of the sky to the city's floor): about 0.6 m each.
const SEGMENTS = 200;

/** Rolled this far down the road, the falls are behind the camera for good: not drawn, though they cull nothing themselves. */
export const FALLS_BEHIND = 30;

export function FallStreaks({ scene }: { scene: Object3D }) {
  const mesh = useRef<Mesh>(null);
  const { geometry, material } = useMemo(() => {
    // Each stream carries on as one rope as wide as it is there, with a thread peeling off beside it.
    const roots: number[] = [];
    const widths: number[] = [];
    const seeds: number[] = [];
    const speeds: number[] = [];
    const rope = (p: Vector3, width: number) => {
      roots.push(p.x, p.y, p.z);
      widths.push(width);
      seeds.push(Math.random());
      speeds.push(2.5 + Math.random());
    };
    for (const { centre, width, points } of streamEnds(scene)) {
      rope(centre, width);
      const edge = points[Math.floor(Math.random() * points.length)];
      rope(centre.clone().lerp(edge, 0.7).setY(JOIN_Y), 0.025 + Math.random() * 0.02);
    }
    const geometry = new InstancedBufferGeometry();
    const position: number[] = [];
    const index: number[] = [];
    for (let j = 0; j <= SEGMENTS; j++) {
      position.push(-1, j / SEGMENTS, 0, 1, j / SEGMENTS, 0);
      if (j < SEGMENTS) index.push(2 * j, 2 * j + 1, 2 * j + 2, 2 * j + 1, 2 * j + 3, 2 * j + 2);
    }
    geometry.setIndex(index);
    geometry.setAttribute('position', new Float32BufferAttribute(position, 3));
    geometry.setAttribute('aRoot', new InstancedBufferAttribute(new Float32Array(roots), 3));
    geometry.setAttribute('aWidth', new InstancedBufferAttribute(new Float32Array(widths), 1));
    geometry.setAttribute('aSeed', new InstancedBufferAttribute(new Float32Array(seeds), 1));
    geometry.setAttribute('aV0', new InstancedBufferAttribute(new Float32Array(speeds), 1));
    geometry.instanceCount = widths.length;
    const linear = (hex: string, k = 1) => new Color(hex).multiplyScalar(k);
    const material = new ShaderMaterial({
      vertexShader,
      fragmentShader,
      uniforms: {
        ...UniformsUtils.clone(UniformsLib.fog),
        uTime: { value: 0 },
        uResX: { value: 1280 },
        uMinPx: { value: 1.4 },
        uIn: { value: 0 },
        uFromSky: { value: 0 },
        // Oil's own colour: next to nothing.
        uBase: { value: linear('#020303') },
        // The sky's colours (components/three/sky.tsx), the city's glow and its windows' green (components/three/city.tsx).
        uZenith: { value: linear('#050a07') },
        uHorizon: { value: linear('#1a3322', 1.6) },
        uGlow: { value: linear('#2f6a3c', 1.4) },
        uLight: { value: new Color(0.62, 1.0, 0.42) },
        // Glints from the city ahead of the landing (+x) and the towers off to its sides.
        uKeyDir: { value: new Vector3(-0.6, 0.1, 0.8).normalize() },
        uRimDir: { value: new Vector3(0.7, -0.05, -0.7).normalize() },
      },
      fog: true,
      transparent: true,
      depthWrite: false,
      // (Both sides: the strip turns to face the camera, but the deck's mirror sees it flipped.)
      side: DoubleSide,
    });
    return { geometry, material };
  }, [scene]);

  useFrame((state) => {
    if (mesh.current) mesh.current.visible = ride.drive.s <= FALLS_BEHIND;
    const u = material.uniforms;
    u.uTime.value = state.clock.elapsedTime;
    u.uResX.value = state.size.width * state.viewport.dpr;
    // Only with the world below (lib/journey.ts belowVisible), coming in as the camera drops beside the falls (the
    // hero is the blog's: the streams end there).
    material.visible = belowVisible(journey.frame) && !devFlag('nofalls');
    u.uIn.value = smoothstep(100, 200, journey.frame);
    // The streams give way to the ropes below the join as they come in (components/three/water.ts).
    waterJoin.value = material.visible ? u.uIn.value : 0;
    // Reaching up into the sky once the planter's mostly gone (they'd pour straight through it), while the streams
    // are still fading (components/three/water.ts), so the two overlap.
    u.uFromSky.value = smoothstep(0.6, 1, waterFromSky.value);
  });

  return <mesh ref={mesh} name="OilFall" geometry={geometry} material={material} frustumCulled={false} renderOrder={2} />;
}
