'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  type BufferGeometry,
  Color,
  type Group,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  InstancedMesh,
  type Light,
  type Material,
  Mesh,
  MeshBasicMaterial,
  type MeshStandardMaterial,
  Object3D,
  PlaneGeometry,
  ShaderMaterial,
  Vector3,
} from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { course, legToWorld, pathAt, ZONES } from '@/lib/course';
import { devFlag } from '@/lib/journey';
import { ENTRY_BLACK, PORTAL_ZONE, PORTALS, portal } from '@/lib/portal';
import { anchors, leftBehind, ride } from '@/lib/ride';
import { zoneEnvMap } from './bike';
import { DRACO_PATH } from './biome';
import { precompile } from './precompile';

// The hive's holes that are ridden through (lib/portal.ts): one of its towers with a lancet opening, black inside
// (art/build-portal.py), across the road where it ends. Falling, the camera draws only one layer: the bike, the eyes and the
// lights. So the world's not hidden piece by piece and costs nothing, and the same lights keep every shader as it was.

const URL = '/models/portal.glb';
/** The layer drawn in the dark. */
const DARK_LAYER = 6;
const BLACK = new Color(0, 0, 0);
const EYES = 240;
/** The block of the dark the eyes repeat in (m). */
const BOX = 150;

const eyeVertex = /* glsl */ `
attribute vec4 aAt;
uniform vec3 uGone;
varying vec2 vQ;
varying vec2 vLook;
varying float vSeed;
varying float vFade;
void main() {
  vec3 rel = mod(aAt.xyz * ${BOX.toFixed(1)} - uGone, ${BOX.toFixed(1)}) - ${(BOX / 2).toFixed(1)};
  vSeed = aAt.w;
  float away = length(rel);
  // (Out of the black in the distance, and never right in the rider's face.)
  vFade = smoothstep(${(BOX / 2).toFixed(1)}, ${(BOX * 0.3).toFixed(1)}, away) * smoothstep(4.0, 10.0, away);
  vec4 view = viewMatrix * vec4(cameraPosition + rel, 1.0);
  float tilt = (aAt.w * 37.0 - floor(aAt.w * 37.0) - 0.5) * 0.9;
  float c = cos(tilt), s = sin(tilt);
  vQ = position.xy;
  view.xy += mat2(c, s, -s, c) * position.xy * (1.8 + 6.0 * aAt.w * aAt.w);
  // Each looks at the rider: toward the middle of the view, as it goes by.
  vLook = mat2(c, -s, s, c) * -normalize(view.xyz).xy;
  gl_Position = projectionMatrix * view;
}`;

const eyeFragment = /* glsl */ `
uniform float uTime;
uniform float uWake;
varying vec2 vQ;
varying vec2 vLook;
varying float vSeed;
varying float vFade;
float eHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void main() {
  // Each opens in its own time, once it's dark, and blinks now and then (components/three/void-gloop.ts's eyes).
  float blink = smoothstep(0.0, 0.25, abs(sin(uTime * (0.25 + 0.3 * vSeed) + vSeed * 40.0)));
  float open = blink * smoothstep(vSeed * 0.7, vSeed * 0.7 + 0.3, uWake);
  float lid = abs(vQ.y) - 0.42 * open * (1.0 - vQ.x * vQ.x / 0.36);
  if (abs(vQ.x) > 0.6 || lid > 0.0) discard;
  vec2 iris = vQ - vLook * 0.2;
  float r = length(iris);
  vec3 c = vec3(0.32, 0.27, 0.22) * (1.0 - smoothstep(0.0, 0.6, abs(vQ.x)));
  float ring = eHash(vec2(floor(atan(iris.y, iris.x) * 7.0), vSeed));
  c = mix(c, mix(vec3(0.55, 0.02, 0.02), vec3(1.0, 0.25, 0.08), ring) * (1.0 - r * 2.5), smoothstep(0.24, 0.2, r));
  c = mix(c, vec3(0.0), smoothstep(0.05, 0.03, abs(iris.x)) * smoothstep(0.22, 0.16, abs(iris.y)));
  gl_FragColor = vec4(c * vFade, 1.0);
  #include <colorspace_fragment>
}`;

function makeEyes() {
  const geometry = new InstancedBufferGeometry();
  const quad = new PlaneGeometry(1.3, 1);
  geometry.index = quad.index;
  geometry.setAttribute('position', quad.attributes.position);
  const at = new Float32Array(EYES * 4);
  const hash = (i: number) => {
    const h = Math.sin(i * 127.1 + 3.7) * 43758.5453;
    return h - Math.floor(h);
  };
  for (let i = 0; i < EYES * 4; i++) at[i] = hash(i + 1);
  geometry.setAttribute('aAt', new InstancedBufferAttribute(at, 4));
  geometry.instanceCount = EYES;
  const material = new ShaderMaterial({
    vertexShader: eyeVertex,
    fragmentShader: eyeFragment,
    uniforms: { uGone: { value: new Vector3() }, uTime: { value: 0 }, uWake: { value: 0 } },
    fog: false,
  });
  const mesh = new Mesh(geometry, material);
  mesh.name = 'PortalEyes';
  mesh.frustumCulled = false;
  mesh.visible = false;
  mesh.layers.set(DARK_LAYER);
  return mesh;
}

function Portals() {
  const { scene } = useGLTF(URL, DRACO_PATH);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const world = useThree((s) => s.scene);
  const root = useRef<Group>(null);

  // One mesh of bone and one of black per tower: its parts, merged. The ones ridden into instanced, one along the road for each.
  const parts = useMemo(() => {
    const env = zoneEnvMap(gl, PORTAL_ZONE);
    const black = new MeshBasicMaterial({ color: BLACK });
    black.name = 'PortalBlack';
    let bone: MeshStandardMaterial | null = null;
    const gather = (prefix: string) => {
      const list: BufferGeometry[] = [];
      for (const part of ['Bone', 'Surround', 'Jamb']) {
        const m = scene.getObjectByName(`${prefix}${part}`) as Mesh;
        list.push(m.geometry);
        bone ??= m.material as MeshStandardMaterial;
      }
      return {
        bone: mergeGeometries(list) as BufferGeometry,
        black: (scene.getObjectByName(`${prefix}Black`) as Mesh).geometry,
      };
    };
    const inOf = gather('PortalEntry');
    const outOf = gather('PortalExit');
    const stone = bone as unknown as MeshStandardMaterial;
    // (As the city's own bone: components/three/zone-city.tsx.)
    stone.envMap = env;
    stone.envMapIntensity = 0.25;
    stone.roughness = 0.82;
    stone.metalness = 0;
    const count = PORTALS.length;
    const intoBone = new InstancedMesh(inOf.bone, stone, count);
    const intoBlack = new InstancedMesh(inOf.black, black, count);
    intoBone.name = 'PortalTowers';
    intoBlack.name = 'PortalHoles';
    intoBone.frustumCulled = intoBlack.frustumCulled = false;
    const out = new Object3D();
    out.name = 'PortalOut';
    out.add(new Mesh(outOf.bone, stone), new Mesh(outOf.black, black));
    out.visible = false;
    return { intoBone, intoBlack, out, stone, black };
  }, [scene, gl]);
  const eyes = useMemo(makeEyes, []);
  useEffect(
    () => () => {
      eyes.geometry.dispose();
      (eyes.material as Material).dispose();
      parts.black.dispose();
    },
    [eyes, parts]
  );

  // Its shaders compiled ahead of time, off to the side, so nothing stalls on first sight; only then is it there to ride into.
  useEffect(() => {
    let live = true;
    const g = root.current;
    if (!g) return;
    g.visible = true;
    eyes.visible = true;
    precompile(gl, g, camera, world)
      .catch(() => {})
      .then(() => {
        if (!live) return;
        g.visible = false;
        eyes.visible = false;
        portal.ready = true;
      });
    return () => {
      live = false;
      portal.ready = false;
    };
  }, [gl, camera, world, eyes]);

  const dummy = useMemo(() => new Object3D(), []);
  const placed = useRef({ at: Number.NaN, first: -1 });
  const dark = useRef({ on: false, mask: 0, background: null as typeof world.background });
  const ahead = useMemo(() => new Vector3(), []);

  /** A tower along the hive's road: u metres along it, in the world. */
  const place = (u: number) => {
    const leg = course.legs[PORTAL_ZONE];
    const at = pathAt(leg.in as NonNullable<typeof leg.in>, u);
    legToWorld(leg, at.x, at.y, dummy.position);
    dummy.rotation.set(0, leg.yaw + at.heading, 0);
    dummy.updateMatrix();
  };

  // (Before the bike and the camera move: as lib/portal.ts left it last frame, which is what they're about to draw.)
  useFrame((state) => {
    const inside = portal.state === 'fall';
    const d = dark.current;
    if (inside !== d.on) {
      d.on = inside;
      eyes.visible = inside;
      if (inside) {
        d.mask = state.camera.layers.mask;
        d.background = world.background;
        world.background = BLACK;
        anchors.bike?.parent?.traverse((o) => o.layers.enable(DARK_LAYER));
        world.traverse((o) => {
          if ((o as Light).isLight) o.layers.enable(DARK_LAYER);
        });
        state.camera.layers.set(DARK_LAYER);
        const leg = course.legs[PORTAL_ZONE];
        const yaw = leg.yaw + pathAt(leg.in as NonNullable<typeof leg.in>, PORTALS[portal.i].enter).heading;
        ahead.set(Math.cos(yaw), 0, -Math.sin(yaw));
      } else {
        state.camera.layers.mask = d.mask;
        world.background = d.background;
      }
    }
    if (inside) {
      const u = (eyes.material as ShaderMaterial).uniforms;
      u.uTime.value = state.clock.elapsedTime;
      u.uWake.value = Math.min(1, portal.t / 1.4);
      // (Falling: they rise past. Riding on as it does: they come on as well.)
      (u.uGone.value as Vector3).copy(ahead).multiplyScalar(portal.along).setY(-portal.down);
    }

    const g = root.current;
    const leg = course.legs[PORTAL_ZONE];
    if (!g || !portal.ready) return;
    g.visible = leg.placed && !!leg.in && (ride.zone === PORTAL_ZONE || ride.zone === PORTAL_ZONE + 1) && !leftBehind(PORTAL_ZONE);
    if (!g.visible) return;
    // The ones still ahead (one that's been ridden through is behind, and gone). Only rewritten when that changes.
    let first = 0;
    while (first < PORTALS.length && ride.drive.s >= leg.at + PORTALS[first].enter) first++;
    const p = placed.current;
    if (p.first !== first || p.at !== leg.at) {
      p.first = first;
      p.at = leg.at;
      for (let i = first; i < PORTALS.length; i++) {
        place(PORTALS[i].enter + ENTRY_BLACK);
        parts.intoBone.setMatrixAt(i - first, dummy.matrix);
        parts.intoBlack.setMatrixAt(i - first, dummy.matrix);
      }
      parts.intoBone.count = parts.intoBlack.count = PORTALS.length - first;
      parts.intoBone.instanceMatrix.needsUpdate = parts.intoBlack.instanceMatrix.needsUpdate = true;
    }
    // The one come out of: only once it has been. It'd stand across the road otherwise.
    parts.out.visible = portal.exit >= 0;
    if (portal.exit >= 0) {
      place(PORTALS[portal.exit].exit);
      parts.out.position.copy(dummy.position);
      parts.out.rotation.copy(dummy.rotation);
    }
  }, -3);

  return (
    <>
      <group ref={root} visible={false}>
        <primitive object={parts.intoBone} />
        <primitive object={parts.intoBlack} />
        <primitive object={parts.out} />
      </group>
      <primitive object={eyes} />
    </>
  );
}

/** Loaded as the hive is (components/three/zone-city.tsx): once the ride's heading for the zone before it. */
export function PortalLoader() {
  const [go, setGo] = useState(false);
  const asked = useRef(false);
  useFrame(() => {
    if (asked.current || ride.mount < 0.5) return;
    if (!(ride.zone > PORTAL_ZONE - 1 || (ride.zone === PORTAL_ZONE - 1 && ride.transition.placed))) return;
    asked.current = true;
    if (!ZONES[PORTAL_ZONE] || devFlag('noportal')) return;
    fetch(URL, { method: 'HEAD' })
      .then((r) => r.ok && setGo(true))
      .catch(() => {});
  });
  return go ? (
    <Suspense fallback={null}>
      <Portals />
    </Suspense>
  ) : null;
}
