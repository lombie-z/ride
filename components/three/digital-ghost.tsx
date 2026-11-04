'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  AdditiveBlending,
  AnimationMixer,
  CanvasTexture,
  type Group,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  type Object3D,
  PlaneGeometry,
  ShaderMaterial,
  Vector3,
} from 'three';
import { MeshSurfaceSampler } from 'three/examples/jsm/math/MeshSurfaceSampler.js';
import { ZONES } from '@/lib/course';
import { isLightDevice } from '@/lib/journey';
import { anchors, featureHere, ride } from '@/lib/ride';
import { DRACO_PATH } from './biome';
import { precompile } from './precompile';

// The core's boost (lib/ride.ts ride.ghost): the bike comes apart into 0s and 1s (blocks of light, in the pixel look), nose first, each lifting off its
// surface (the bike's own materials are cut away in the same blocks as they go, components/three/bike.tsx), and they stream back
// past the rider in a tunnel while something runs just ahead of the view in the bike's place, flickering. Going back, the
// same run in reverse. All in the bike's own frame (+x ahead, +y up): a child of the ridden group.

const CREATURE = '/models/creature.glb';
/** Where it runs, from the bike's middle (m ahead): right under the rider, its back beneath the eye, ridden in the bike's place. */
const RUN_AHEAD = 0.2;
/** How big it is against the model's own (2.6 m long): its back just under the rider's eye. */
const RUN_SCALE = 1.08;
/** Its tail, shortened: at full length it reaches back past the rider's eye. */
const TAIL_SCALE = 0.5;
/** How fast its legs may go, however fast the ride (the clip's speed, times this at most). */
const MAX_STRIDE = 2.4;

/** How many blocks it comes apart into. */
const digitCount = () => (isLightDevice() ? 1400 : 3600);

function digitAtlas() {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 64;
  const g = canvas.getContext('2d') as CanvasRenderingContext2D;
  g.fillStyle = '#000';
  g.fillRect(0, 0, 128, 64);
  g.fillStyle = '#fff';
  g.font = 'bold 58px monospace';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillText('0', 32, 34);
  g.fillText('1', 96, 34);
  return new CanvasTexture(canvas);
}

const digits = { base: null as Float32Array | null, attribute: null as InstancedBufferAttribute | null, sampled: false };
const toBike = new Matrix4();
const at = new Vector3();

/**
 * Where the digits start: points scattered over a bike's surface, in the bike's frame (each zone's built in the same one).
 * `frame`: the ridden group the bike's a child of.
 */
export function sampleDigits(bike: Object3D, frame: Object3D) {
  const count = digitCount();
  digits.base ??= new Float32Array(count * 3);
  const meshes: Mesh[] = [];
  bike.traverse((o) => {
    const m = o as Mesh;
    const name = (m.material as { name?: string } | undefined)?.name ?? '';
    if (m.isMesh && !/Glass|Smoke|Glyph/.test(name) && m.geometry.index !== undefined) meshes.push(m);
  });
  if (!meshes.length) return;
  frame.updateWorldMatrix(true, false);
  bike.updateWorldMatrix(true, true);
  toBike.copy(frame.matrixWorld).invert();
  const samplers = meshes.map((m) => new MeshSurfaceSampler(m).build());
  // (Shared out by triangles: near enough to by area for a bike.)
  const weights = meshes.map((m) => (m.geometry.index ? m.geometry.index.count : (m.geometry.attributes.position?.count ?? 0)) / 3);
  const total = weights.reduce((a, b) => a + b, 0);
  let i = 0;
  for (const [n, sampler] of samplers.entries()) {
    const share = n === samplers.length - 1 ? count - i : Math.round((count * weights[n]) / total);
    for (let j = 0; j < share && i < count; j++, i++) {
      sampler.sample(at);
      at.applyMatrix4(meshes[n].matrixWorld).applyMatrix4(toBike);
      digits.base.set([at.x, at.y, at.z], i * 3);
    }
  }
  digits.sampled = true;
  if (digits.attribute) digits.attribute.needsUpdate = true;
}

function Digits() {
  const uniforms = useMemo(() => ({ uAmount: { value: 0 }, uTime: { value: 0 }, uAtlas: { value: digitAtlas() } }), []);
  const mesh = useMemo(() => {
    const count = digitCount();
    const g = new InstancedBufferGeometry();
    g.copy(new PlaneGeometry(1, 1) as unknown as InstancedBufferGeometry);
    g.instanceCount = count;
    digits.base ??= new Float32Array(count * 3);
    digits.attribute = new InstancedBufferAttribute(digits.base, 3);
    g.setAttribute('aBase', digits.attribute);
    const seeds = new Float32Array(count * 4);
    for (let i = 0; i < count * 4; i++) seeds[i] = Math.random();
    g.setAttribute('aSeed', new InstancedBufferAttribute(seeds, 4));
    const material = new ShaderMaterial({
      uniforms,
      transparent: true,
      depthWrite: false,
      blending: AdditiveBlending,
      toneMapped: false,
      vertexShader: /* glsl */ `
        attribute vec3 aBase;
        attribute vec4 aSeed;
        uniform float uAmount;
        uniform float uTime;
        varying vec2 vUv;
        varying float vLight;
        void main() {
          // Each comes away in its turn: the nose first, back to the rider's own hands (as the bike's cut away, bike.tsx).
          float order = clamp((1.45 - aBase.x) / 2.9, 0.0, 1.0);
          float k = clamp((uAmount - order * 0.45) / 0.55, 0.0, 1.0);
          k = k * k * (3.0 - 2.0 * k);
          // Streaming back past the rider, in a tube round the view: from far ahead, gone behind.
          float flow = fract(aSeed.y + uTime * (0.8 + 1.4 * aSeed.z));
          float ang = aSeed.w * 6.28318;
          float tube = 1.5 + 2.6 * aSeed.x * aSeed.x;
          vec3 stream = vec3(14.0 - 19.0 * flow, 1.3 + sin(ang) * tube * 0.8, cos(ang) * tube * 1.25);
          vec3 lift = aBase + vec3(0.0, 0.15 + 0.45 * aSeed.z, (aSeed.w - 0.5) * 0.5) * smoothstep(0.0, 0.5, k);
          vec3 p = mix(lift, stream, smoothstep(0.25, 1.0, k));
          vec4 mv = modelViewMatrix * vec4(p, 1.0);
          float size = mix(0.028, 0.075 + 0.07 * aSeed.z, k);
          // (0 or 1, flipping now and then.)
          float glyph = step(0.5, fract(aSeed.x * 7.0 + floor(uTime * (2.0 + 9.0 * aSeed.z)) * 0.37));
          mv.xy += position.xy * size * vec2(0.75, 1.0);
          gl_Position = projectionMatrix * mv;
          vUv = (uv + vec2(glyph, 0.0)) * vec2(0.5, 1.0);
          // (Out only once it's begun, none left when it's done; thinned right by the eye, where one would fill the view.)
          float near = smoothstep(0.25, 1.0, -mv.z);
          vLight = step(0.002, k) * near * (0.55 + 1.6 * aSeed.y * aSeed.y) * (0.6 + 0.4 * sin(uTime * 30.0 * aSeed.z + aSeed.x * 40.0));
        }`,
      fragmentShader: /* glsl */ `
        uniform sampler2D uAtlas;
        varying vec2 vUv;
        varying float vLight;
        void main() {
          float a = texture2D(uAtlas, vUv).r;
          if (a < 0.2 || vLight <= 0.001) discard;
          gl_FragColor = vec4(vec3(0.3, 1.0, 0.42) * a * vLight * 2.2, 1.0);
        }`,
    });
    const m = new Mesh(g, material);
    m.frustumCulled = false;
    m.renderOrder = 9;
    m.visible = false;
    return m;
  }, [uniforms]);
  useEffect(
    () => () => {
      mesh.geometry.dispose();
      (mesh.material as ShaderMaterial).dispose();
      uniforms.uAtlas.value.dispose();
      digits.attribute = null;
    },
    [mesh, uniforms]
  );
  useFrame((state) => {
    // (The core's bike samples itself when it's loaded, components/three/bike.tsx; anywhere else, dev, whichever's there.)
    if (!digits.sampled && featureHere() === 'ghost' && anchors.bike?.parent) sampleDigits(anchors.bike, anchors.bike.parent);
    const { amount } = ride.ghost;
    mesh.visible = amount > 0.001;
    if (!mesh.visible) return;
    uniforms.uAmount.value = amount;
    uniforms.uTime.value = state.clock.elapsedTime;
  });
  return <primitive object={mesh} />;
}

/** The thing that runs in the bike's place: a skinned creature (art/build-creature.py) drawn as a failing hologram. */
function Creature() {
  const { scene, animations } = useGLTF(CREATURE, DRACO_PATH);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const world = useThree((s) => s.scene);
  const group = useRef<Group>(null);
  const uniforms = useMemo(() => ({ uTime: { value: 0 }, uFlick: { value: 1 }, uAmount: { value: 0 } }), []);
  const mixer = useMemo(() => new AnimationMixer(scene), [scene]);
  useEffect(() => {
    const clip = animations.find((a) => a.name === 'Run') ?? animations[0];
    if (clip) mixer.clipAction(clip).play();
    const material = new MeshBasicMaterial({ color: 0xffffff, transparent: true, toneMapped: false, fog: false });
    material.onBeforeCompile = (shader) => {
      Object.assign(shader.uniforms, uniforms);
      shader.vertexShader = shader.vertexShader
        .replace(
          '#include <common>',
          `#include <common>
uniform float uTime;
varying vec3 vBody;
varying vec3 vView;`
        )
        .replace(
          '#include <project_vertex>',
          `// Slices of it slip sideways, a different few each moment.
float slice = floor(transformed.y * 9.0 + floor(uTime * 22.0) * 3.1);
transformed.z += step(0.9, fract(sin(slice * 91.7) * 4375.5)) * 0.12 * (fract(sin(slice * 13.1) * 917.3) - 0.5);
vBody = transformed;
#include <project_vertex>
vView = -mvPosition.xyz;`
        );
      shader.fragmentShader = shader.fragmentShader
        .replace(
          '#include <common>',
          `#include <common>
uniform float uTime;
uniform float uFlick;
uniform float uAmount;
varying vec3 vBody;
varying vec3 vView;`
        )
        .replace(
          '#include <dithering_fragment>',
          `#include <dithering_fragment>
// Comes and goes in blocks, with the bike's.
vec3 cell = floor(vBody * 14.0);
float h = fract(sin(dot(cell, vec3(12.9898, 78.233, 37.719))) * 43758.5453);
if (h > uAmount * 1.2 - 0.1) discard;
// Faceted, its rim lit; a dim body, scanlines running over it, columns of light falling down it.
vec3 n = normalize(cross(dFdx(vView), dFdy(vView)));
float rim = pow(1.0 - abs(dot(n, normalize(vView))), 1.6);
float scan = 0.65 + 0.35 * step(0.5, fract(vBody.y * 26.0 - uTime * 5.0));
float col = floor(vBody.x * 16.0 + vBody.z * 11.0);
float fall = pow(fract(vBody.y * 0.9 + uTime * (1.2 + fract(col * 0.37) * 2.0) + fract(col * 0.71)), 6.0);
float glow = (0.75 * rim + 1.5 * fall) * scan;
// (Nearly black inside, its edges and falling light white-green: the world's gone green by now, and it has to stand out of it.)
vec3 lit = vec3(0.35, 1.0, 0.5) * glow * (0.5 + 1.7 * uFlick) + vec3(0.9, 1.0, 0.9) * rim * rim * rim * 1.6 * uFlick;
gl_FragColor = vec4(vec3(0.004, 0.03, 0.012) + lit, 0.4 + 0.6 * uFlick);`
        );
    };
    material.customProgramCacheKey = () => 'digital-ghost';
    scene.traverse((o) => {
      const m = o as Mesh;
      if (m.isMesh) {
        m.material = material;
        m.frustumCulled = false;
      }
    });
    const g = group.current;
    if (g) {
      g.visible = true;
      precompile(gl, g, camera, world)
        .catch(() => {})
        .then(() => {
          g.visible = false;
        });
    }
    return () => {
      material.dispose();
      mixer.stopAllAction();
    };
  }, [scene, animations, mixer, uniforms, gl, camera, world]);

  const flicker = useRef({ until: 0, level: 1, jump: 0 });
  useFrame((state, delta) => {
    const g = group.current;
    if (!g) return;
    const { amount, state: st } = ride.ghost;
    g.visible = amount > 0.02;
    if (!g.visible) return;
    const t = state.clock.elapsedTime;
    uniforms.uTime.value = t;
    uniforms.uAmount.value = amount;
    // It flickers: long enough at each brightness to see it, cut now and then near to nothing, and it jumps.
    const f = flicker.current;
    if (t > f.until) {
      const r = Math.random();
      f.level = r < 0.14 ? 0.03 : r < 0.4 ? 0.38 : 1;
      f.until = t + (r < 0.14 ? 0.035 : 0.03 + Math.random() * 0.11);
      f.jump = r < 0.14 ? (Math.random() - 0.5) * 0.5 : r < 0.3 ? (Math.random() - 0.5) * 0.14 : 0;
    }
    uniforms.uFlick.value = f.level;
    // Its stride follows the ride up, to a point; it hangs a little further ahead as it gets going, drifting across the road.
    mixer.update(delta * Math.min(MAX_STRIDE, 1 + ride.drive.speed / 120) * (st === 'back' ? 0.7 : 1));
    scene.getObjectByName('Tail1')?.scale.setScalar(TAIL_SCALE);
    // (Hardly moving under the rider: a small sway, and when it flickers a small jump.)
    g.position.set(RUN_AHEAD, 0.02, f.jump * 0.2 + 0.03 * Math.sin(t * 1.9));
    g.rotation.y = 0.03 * Math.sin(t * 1.9);
  });
  return (
    <group ref={group} visible={false}>
      <primitive object={scene} scale={RUN_SCALE} />
    </group>
  );
}

/** Loads the creature once the ride's heading for the core (or a dev ?feature=ghost), if it's been built. */
function CreatureLoader() {
  const [go, setGo] = useState(false);
  const asked = useRef(false);
  useFrame(() => {
    if (asked.current || ride.mount < 0.5) return;
    const heading = ride.zone >= ZONES.length - 2 || featureHere() === 'ghost';
    if (!heading) return;
    asked.current = true;
    fetch(CREATURE, { method: 'HEAD' })
      .then((r) => r.ok && setGo(true))
      .catch(() => {});
  });
  return go ? (
    <Suspense fallback={null}>
      <Creature />
    </Suspense>
  ) : null;
}

/** All of the boost's own parts, in the bike's frame. */
export function DigitalGhost() {
  return (
    <>
      <Digits />
      <CreatureLoader />
    </>
  );
}
