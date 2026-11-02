'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo } from 'react';
import { BufferAttribute, BufferGeometry, Color, type Mesh, type Object3D, ShaderMaterial, Vector3 } from 'three';
import { isLightDevice, journey, smoothstep } from '@/lib/journey';
import { JOIN_Y, OIL_FLOOR, streamEnds } from './fall-streaks';
import { waterFromSky } from './water';

// Spray and mist as GPU particles. Each particle loops through its own short life: it starts at aStart, moves with
// aVelocity under gravity, and fades in and out. One material, tuned per system.

const vertexShader = /* glsl */ `
uniform float uTime;
uniform float uGravity;
uniform float uScale;
attribute vec3 aStart;
attribute vec3 aVelocity;
attribute float aPhase;
attribute float aLife;
attribute float aSize;
varying float vAlpha;
varying float vSeed;
void main() {
  float t = fract(uTime / aLife + aPhase) * aLife;
  float k = t / aLife;
  vec3 p = aStart + aVelocity * t + vec3(0.0, 0.5 * uGravity * t * t, 0.0);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  // Size in world units, so near drops are big and far ones are specks.
  gl_PointSize = aSize * uScale * projectionMatrix[1][1] / -mv.z;
  vAlpha = sin(3.14159 * k) * smoothstep(0.03, 0.4, -mv.z);
  vSeed = aPhase * 37.0;
}`;

const fragmentShader = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
uniform float uSoftness;
varying float vAlpha;
varying float vSeed;
float sHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float sNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(sHash(i), sHash(i + vec2(1, 0)), u.x), mix(sHash(i + vec2(0, 1)), sHash(i + vec2(1, 1)), u.x), u.y);
}
void main() {
  float d = length(gl_PointCoord - 0.5) * 2.0;
  float a = 1.0 - smoothstep(1.0 - uSoftness, 1.0, d);
  // Soft sprites (mist) get billows: noise inside the disc, each particle its own.
  if (uSoftness > 0.9) {
    vec2 q = gl_PointCoord * 3.0 + vSeed;
    float b = sNoise(q) * 0.6 + sNoise(q * 2.3) * 0.3 + sNoise(q * 5.1) * 0.1;
    a *= smoothstep(0.38, 0.58, b + (1.0 - d) * 0.35);
  }
  // Soft sprites are lit from above: brighter crowns, shadowed undersides.
  vec3 colour = uColor * (uSoftness > 0.9 ? mix(0.78, 1.12, 1.0 - gl_PointCoord.y) : 1.0);
  gl_FragColor = vec4(colour, a * vAlpha * uOpacity);
  #include <colorspace_fragment>
}`;

interface System {
  count: number;
  /** Writes one particle's start, velocity, life (s) and size (m). */
  emit: (i: number, start: Vector3, velocity: Vector3) => { life: number; size: number };
  gravity: number;
  color: string | Color;
  opacity: number;
  softness: number;
}

function particles({ count, emit, gravity, color, opacity, softness }: System) {
  const start = new Float32Array(count * 3);
  const velocity = new Float32Array(count * 3);
  const phase = new Float32Array(count);
  const life = new Float32Array(count);
  const size = new Float32Array(count);
  const s = new Vector3();
  const v = new Vector3();
  for (let i = 0; i < count; i++) {
    const p = emit(i, s.set(0, 0, 0), v.set(0, 0, 0));
    s.toArray(start, i * 3);
    v.toArray(velocity, i * 3);
    phase[i] = Math.random();
    life[i] = p.life;
    size[i] = p.size;
  }
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(count * 3), 3));
  geometry.setAttribute('aStart', new BufferAttribute(start, 3));
  geometry.setAttribute('aVelocity', new BufferAttribute(velocity, 3));
  geometry.setAttribute('aPhase', new BufferAttribute(phase, 1));
  geometry.setAttribute('aLife', new BufferAttribute(life, 1));
  geometry.setAttribute('aSize', new BufferAttribute(size, 1));
  const material = new ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: {
      uTime: { value: 0 },
      uGravity: { value: gravity },
      uScale: { value: 1 },
      uColor: { value: new Color(color) },
      uOpacity: { value: opacity },
      uSoftness: { value: softness },
    },
    transparent: true,
    depthWrite: false,
  });
  return { geometry, material };
}

/** Random points on the falling water (where it's falling, not still), with their outward normals. */
function fallSurface(scene: Object3D) {
  const points: { p: Vector3; n: Vector3 }[] = [];
  scene.updateMatrixWorld(true);
  scene.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh || !mesh.name.startsWith('Fall') || mesh.name.startsWith('FallMain')) return;
    const g = mesh.geometry;
    const pos = g.getAttribute('position');
    const nor = g.getAttribute('normal');
    const flow = g.getAttribute('_flow');
    const fade = g.getAttribute('_fade');
    for (let i = 0; i < pos.count; i += 3) {
      // Only where the water is falling and fully there (not the still channel, nor where the streams fade out).
      if ((flow && flow.getX(i) < 0.5) || (fade && fade.getX(i) < 0.95)) continue;
      const p = new Vector3().fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
      // (Only above where the ropes take over: components/three/fall-streaks.tsx.)
      if (p.y < JOIN_Y) continue;
      const n = new Vector3().fromBufferAttribute(nor, i).transformDirection(mesh.matrixWorld);
      points.push({ p, n });
    }
  });
  return points;
}

const GRAVITY = 9.8;

export function Spray({ scene }: { scene: Object3D }) {
  const systems = useMemo(() => {
    const share = isLightDevice() ? 0.45 : 1;
    const surface = fallSurface(scene);
    const pick = () => surface[Math.floor(Math.random() * surface.length)];
    // The oil ropes carry on from the streams' ends (components/three/fall-streaks.tsx).
    const ends = streamEnds(scene);
    const end = () => ends[Math.floor(Math.random() * ends.length)].centre;
    const streams = particles({
      count: Math.round(2600 * share),
      gravity: -3,
      color: '#0b0c0d',
      opacity: 0.9,
      softness: 0.5,
      // Black drops peeling off the falls and dropping away.
      emit: (_, start, velocity) => {
        const { p, n } = pick();
        start.copy(p).addScaledVector(n, 0.01);
        velocity
          .copy(n)
          .multiplyScalar(0.12 + Math.random() * 0.25)
          .add(new Vector3(0, -0.9, 0));
        return { life: 0.5 + Math.random() * 0.6, size: 0.006 + Math.random() * 0.012 };
      },
    });
    // (They go with the streams, as the planter goes: components/three/water.ts.)
    streams.material.userData.opacity = () => 0.9 * (1 - smoothstep(0.4, 1, waterFromSky.value));
    const shed = particles({
      count: Math.round(1200 * share),
      gravity: -GRAVITY,
      color: '#0b0c0d',
      opacity: 0.95,
      softness: 0.4,
      // Beads of oil shed by the ropes on the way down, falling with them.
      emit: (_, start, velocity) => {
        const p = end();
        const drop = 2 + Math.random() ** 1.5 * 60;
        const a = Math.random() * Math.PI * 2;
        start.set(p.x + Math.cos(a) * 0.08, p.y - drop, p.z + Math.sin(a) * 0.08);
        velocity
          .set(Math.cos(a), 0, Math.sin(a))
          .multiplyScalar(0.2 + Math.random() * 0.6)
          .add(new Vector3(0, -Math.sqrt(16 + 2 * GRAVITY * drop) * (0.8 + Math.random() * 0.2), 0));
        return { life: 0.4 + Math.random() * 0.5, size: 0.025 + Math.random() * 0.05 };
      },
    });
    const splash = particles({
      count: Math.round(1400 * share),
      gravity: -GRAVITY,
      color: '#0b0c0d',
      opacity: 0.95,
      softness: 0.5,
      // Kicked up where the ropes hit the city's floor.
      emit: (_, start, velocity) => {
        const p = end();
        const a = Math.random() * Math.PI * 2;
        const r = Math.random() * 0.6;
        start.set(p.x + Math.cos(a) * r, OIL_FLOOR + 0.05, p.z + Math.sin(a) * r);
        velocity
          .set(Math.cos(a), 0, Math.sin(a))
          .multiplyScalar(0.5 + Math.random() * 1.1)
          .add(new Vector3(0, 2 + Math.random() * 5, 0));
        return { life: 0.6 + Math.random() * 0.6, size: 0.04 + Math.random() * 0.1 };
      },
    });
    // (With the ropes, as the camera drops beside the falls.)
    shed.material.userData.opacity = splash.material.userData.opacity = () => 0.95 * smoothstep(100, 200, journey.frame);
    return [streams, shed, splash];
  }, [scene]);

  useFrame((state) => {
    for (const { material } of systems) {
      material.uniforms.uTime.value = state.clock.elapsedTime;
      if (material.userData.opacity) material.uniforms.uOpacity.value = material.userData.opacity();
      material.uniforms.uScale.value = state.size.height * state.viewport.dpr * 0.5;
    }
  });

  return (
    <>
      {systems.map(({ geometry, material }) => (
        <points key={material.uuid} name="Spray" geometry={geometry} material={material} frustumCulled={false} renderOrder={4} />
      ))}
    </>
  );
}
