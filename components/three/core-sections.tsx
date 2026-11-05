'use client';

import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import {
  type AnimationAction,
  AnimationMixer,
  type Camera,
  Color,
  Group,
  InstancedMesh,
  type Material,
  Matrix4,
  type Mesh,
  type MeshStandardMaterial,
  type Object3D,
  type Scene,
  type Texture,
  Vector3,
  type WebGLRenderer,
} from 'three';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { course } from '@/lib/course';
import { doorOpen, doorState, hallShown } from '@/lib/doors';
import { smoothstep } from '@/lib/journey';
import { look } from '@/lib/look';
import { ride, startAt } from '@/lib/ride';
import { sectionImpact } from '@/lib/section-audio';
import { SECTION_TABLE, type SectionId, sectionAt, sections } from '@/lib/sections';
import { zoneEnvMap } from './bike';
import { DRACO_PATH } from './biome';
import { precompile } from './precompile';

// The stairwell and flooded tunnel (art/core/SECTIONS.md) on the site: each its own glb in the core's frame, loaded ahead of being needed,
// shown while it's the section the ride can see, and dropped after, GPU and all. The one that's drawn is the road's: the join's sealed black
// at each end (the stair's glb has the flood's first 80 m). Their door, the tunnel's bulkhead, turns on doorState (lib/doors.ts), and the
// stairwell's moving pieces are scrubbed by how far the ride's got along their stretch of road.

/** Metres short of the stairwell's top it starts loading, and how far down the stairwell the tunnel does. */
const LOAD = { stair: 500, flood: 300 };
/** How far into the hall the tunnel's dropped (m). */
const DROP_FLOOD = 40;
/** The instanced pieces, in cells so those out of view aren't drawn: x and z, and y (the stairwell's stacked up its shaft). */
const CELLS: Record<SectionId, [number, number]> = { stair: [48, 26], flood: [72, 1000] };
/** How far the bulkhead's wheel steps round on each win (radians), and how quickly. */
const WHEEL_STEP = Math.PI / 2;
const WHEEL_RATE = 5;
/** Its lamps, lit by each win. */
const LAMP_LIT = { r: 1, g: 0.1, b: 0.02, strength: 2.6 };

// (As the core's own, components/three/zone-city.tsx.)
const CORE_KINDS = ['Panel', 'Red', 'Led', 'Screen', 'Code', 'Heart', 'Fluid', 'TankGlass', 'Mist'];
const GLOWS = ['Panel', 'Red', 'Led', 'Screen', 'Code', 'Heart', 'Fluid'];

let loader: GLTFLoader | null = null;
const gltf = () => {
  if (!loader) {
    const draco = new DRACOLoader();
    draco.setDecoderPath(DRACO_PATH);
    loader = new GLTFLoader();
    loader.setDRACOLoader(draco);
  }
  return loader;
};

/** Its materials, as the core's are: its dark's reflections, its lights past white. */
function dress(root: Object3D, env: Texture) {
  root.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh) return;
    const m = mesh.material as MeshStandardMaterial;
    if (m.userData.dressed) return;
    m.userData.dressed = true;
    m.envMap = env;
    m.envMapIntensity = 1.2;
    const name = m.name.startsWith('City5') ? m.name.slice(5) : m.name;
    const kind = CORE_KINDS.find((e) => name.endsWith(e)) ?? name;
    if (GLOWS.includes(kind)) m.toneMapped = false;
    if (kind === 'Fluid' || kind === 'TankGlass') m.depthWrite = false;
    if (kind === 'TankGlass') m.envMapIntensity = 2;
    if (/Floor|Wet/.test(kind)) m.envMapIntensity = 0.12;
    // (Its water reflects what's around it, not the core's dark room: components/three/section-fx-water.ts.)
    if (kind === 'Water') m.envMapIntensity = 0;
    m.needsUpdate = true;
  });
}

/** Its instanced pieces (the glb's GPU instancing, each along all of it) gathered into cells, for the camera to leave out those it can't see. */
function intoCells(root: Object3D, id: SectionId) {
  root.updateMatrixWorld(true);
  const toRoot = new Matrix4().copy(root.matrixWorld).invert();
  const [wide, high] = CELLS[id];
  const sources: InstancedMesh[] = [];
  root.traverse((o) => {
    if ((o as InstancedMesh).isInstancedMesh) sources.push(o as InstancedMesh);
  });
  const each = new Matrix4();
  const centre = new Vector3();
  for (const im of sources) {
    const base = toRoot.clone().multiply(im.matrixWorld);
    const cells = new Map<string, Matrix4[]>();
    for (let i = 0; i < im.count; i++) {
      im.getMatrixAt(i, each);
      const m = base.clone().multiply(each);
      centre.setFromMatrixPosition(m);
      const key = `${Math.floor(centre.x / wide)},${Math.floor(centre.y / high)},${Math.floor(centre.z / wide)}`;
      if (!cells.has(key)) cells.set(key, []);
      (cells.get(key) as Matrix4[]).push(m);
    }
    for (const matrices of cells.values()) {
      const one = new InstancedMesh(im.geometry, im.material, matrices.length);
      one.name = `${(im.material as Material).name}Instances`;
      for (const [i, m] of matrices.entries()) one.setMatrixAt(i, m);
      one.computeBoundingSphere();
      root.add(one);
    }
    im.removeFromParent();
    im.dispose();
  }
}

/** Everything it holds on the GPU, as it's dropped. */
function dispose(root: Object3D) {
  const textures = new Set<Texture>();
  const materials = new Set<Material>();
  root.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh) return;
    mesh.geometry.dispose();
    if ((o as InstancedMesh).isInstancedMesh) (o as InstancedMesh).dispose();
    materials.add(mesh.material as Material);
  });
  for (const m of materials) {
    for (const v of Object.values(m as unknown as Record<string, unknown>))
      if ((v as Texture)?.isTexture && v !== (m as MeshStandardMaterial).envMap) textures.add(v as Texture);
    m.dispose();
  }
  for (const t of textures) t.dispose();
}

type Mover = { asset: string; root: Object3D; mixer: AnimationMixer; action: AnimationAction; from: number; to: number; last: number; fired: boolean };

/** Each moving piece's sound (lib/section-audio.ts), and how far through its clip it's made: a flight and its chunks as they go, a beam and a shutter as they hit. */
const IMPACTS: Record<string, { kind: 'metal' | 'collapse' | 'debris'; at: number }> = {
  flight_collapse: { kind: 'collapse', at: 0.05 },
  debris_set: { kind: 'debris', at: 0.05 },
  beam_swing: { kind: 'metal', at: 0.7 },
  shutter_slam: { kind: 'metal', at: 0.8 },
};
const eye = new Vector3();
const piece = new Vector3();
const toPiece = new Vector3();
const right = new Vector3();

/** The stairwell's moving pieces: each asset's glb, a copy at each of its empties (City5.Moving.<asset>.<i>), its clip paused to be scrubbed. */
async function loadMovers(stair: Object3D, env: Texture) {
  const empties: Object3D[] = [];
  stair.traverse((o) => {
    if (typeof o.userData.asset === 'string' && o.name.startsWith('City5Moving')) empties.push(o);
  });
  const names = [...new Set(empties.map((e) => e.userData.asset as string))];
  const assets = new Map(await Promise.all(names.map(async (n) => [n, await gltf().loadAsync(`/models/sections/${n}.glb`)] as const)));
  const movers: Mover[] = [];
  const from = sections.stair.from;
  for (const e of empties) {
    const a = assets.get(e.userData.asset as string);
    if (!a) continue;
    const root = a.scene.clone(true);
    root.position.copy(e.position);
    root.quaternion.copy(e.quaternion);
    dress(root, env);
    stair.add(root);
    const mixer = new AnimationMixer(root);
    const action = mixer.clipAction(a.animations[0]);
    action.play();
    action.paused = true;
    movers.push({
      asset: e.userData.asset as string,
      root,
      mixer,
      action,
      from: from + (e.userData.s0 as number),
      to: from + (e.userData.s1 as number),
      last: -1,
      fired: false,
    });
  }
  return movers;
}

type Held = {
  root: Group;
  movers: Mover[];
  stump: Object3D | null;
  door: Object3D | null;
  wheel: Object3D | null;
  lamps: MeshStandardMaterial[];
  sealFar: Object3D | null;
  wheelAngle: number;
};

async function loadSection(id: SectionId, gl: WebGLRenderer, camera: Camera, world: Scene): Promise<Held> {
  const env = zoneEnvMap(gl, 4);
  const { scene } = await gltf().loadAsync(SECTION_TABLE[id].url);
  dress(scene, env);
  intoCells(scene, id);
  const movers = id === 'stair' ? await loadMovers(scene, env) : [];
  const root = new Group();
  root.name = `CoreSection${id}`;
  root.visible = false;
  root.add(scene);
  const door = scene.getObjectByName('City5BulkheadDoor') ?? null;
  const lamps: MeshStandardMaterial[] = [];
  let wheel: Object3D | null = null;
  door?.traverse((o) => {
    const m = (o as Mesh).material as MeshStandardMaterial | undefined;
    const lamp = m?.name.match(/BulkheadLamp(\d)/);
    if (lamp && m) lamps[Number(lamp[1]) - 1] = m;
    // (The wheel's the part with its own origin, at its hub: the rest are at the hinge.)
    if (o !== door && o.position.length() > 0.5) wheel = o;
  });
  // Compiled and uploaded in the background: first seen, they'd stall that frame.
  const textures = new Set<Texture>();
  scene.traverse((o) => {
    const m = (o as Mesh).material as (Material & Record<string, unknown>) | undefined;
    for (const v of Object.values(m ?? {})) if ((v as Texture)?.isTexture) textures.add(v as Texture);
  });
  await precompile(gl, root, camera, world).catch(() => {});
  for (const t of textures) gl.initTexture(t);
  return {
    root,
    movers,
    stump: scene.getObjectByName('City5stair_flight_torni') ?? scene.getObjectByName('City5stair_flight_torn.i') ?? null,
    door,
    wheel,
    lamps,
    sealFar: scene.getObjectByName('City5SealFar') ?? null,
    wheelAngle: 0,
  };
}

/** Drops a section, GPU and all. */
function dropSection(held: Record<SectionId, Held | null>, id: SectionId) {
  const h = held[id];
  if (!h) return;
  h.root.removeFromParent();
  for (const m of h.movers) m.mixer.stopAllAction();
  dispose(h.root);
  held[id] = null;
  sections.ready[id] = false;
  sections.scene[id] = null;
}

const air = new Color();
const TAU = 2 * Math.PI;
const DEGREES = Math.PI / 180;

export function CoreSections() {
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const world = useThree((s) => s.scene);
  const holder = useRef<Group>(null);
  const held = useRef<Record<SectionId, Held | null>>({ stair: null, flood: null });
  const loading = useRef<Record<SectionId, boolean>>({ stair: false, flood: false });
  const wanted = useRef<Record<SectionId, boolean>>({ stair: false, flood: false });
  const started = useRef(false);

  // (Dropped with the city, or a hot reload of this file.)
  useEffect(
    () => () => {
      dropSection(held.current, 'stair');
      dropSection(held.current, 'flood');
    },
    []
  );

  const load = (id: SectionId) => {
    if (loading.current[id] || held.current[id]) return;
    loading.current[id] = true;
    loadSection(id, gl, camera, world)
      .then((h) => {
        loading.current[id] = false;
        // (No longer wanted by the time it's come: got off, or gone on.)
        if (!wanted.current[id] || !holder.current) {
          dispose(h.root);
          return;
        }
        holder.current.add(h.root);
        held.current[id] = h;
        sections.scene[id] = h.root;
        sections.ready[id] = true;
      })
      .catch((e) => {
        loading.current[id] = false;
        console.warn(`The ${id} section didn't load`, e);
      });
  };

  useFrame((_, delta) => {
    if (!sections.spliced) return;
    const leg = course.legs[4];
    const placed = ride.zone === 4 && leg.placed;
    // (How far along the core's road: where it's headed to, if it's starting there.)
    started.current ||= placed;
    const pending = !placed && !started.current && startAt?.k === 4 && startAt.s !== null;
    const u = placed ? ride.drive.s - leg.at : pending ? (startAt?.s as number) : Number.NEGATIVE_INFINITY;
    const { stair, flood, hallFrom } = sections;
    // (Past what's drawn, down here, the air's colour rather than the canvas's: from before the lab's doors, seen through them open.)
    if (placed && u >= stair.from - LOAD.stair) {
      // (Nearly black round the doors, where it's seen through the gaps beside them, then the stairwell's own air.)
      air.copy(look.haze).multiplyScalar(0.12 + 0.88 * smoothstep(stair.from + 20, stair.from + 70, u));
      world.background = air;
    } else if (world.background === air) world.background = null;
    wanted.current.stair = u > stair.from - LOAD.stair && u < stair.to;
    wanted.current.flood = u > stair.from + LOAD.flood && u < hallFrom + DROP_FLOOD;
    for (const id of ['stair', 'flood'] as const) {
      if (wanted.current[id]) load(id);
      else dropSection(held.current, id);
    }
    const a = held.current.stair;
    const b = held.current.flood;
    // The lab's doors opening onto the stair; the swap's at the water, where both have the same tube.
    if (a) a.root.visible = doorOpen(1) > 0 || sectionAt(u) === 'stair';
    if (b) b.root.visible = u >= flood.from;
    if (a?.root.visible) {
      for (const m of a.movers) {
        const t = Math.min(1, Math.max(0, (u - m.from) / (m.to - m.from)));
        if (m.asset === 'debris_set') m.root.visible = t > 0 && t < 1;
        if (m.asset === 'flight_collapse') m.root.visible = t < 1;
        const impact = IMPACTS[m.asset];
        if (impact && !m.fired && t >= impact.at) {
          m.fired = true;
          // (Not one it's started past, `?at=`. As it hits: off to the side it's on, quieter from further off.)
          if (m.last >= 0) {
            camera.getWorldPosition(eye);
            toPiece.copy(m.root.getWorldPosition(piece)).sub(eye);
            const far = toPiece.length();
            sectionImpact(impact.kind, Math.max(0.35, 1 - far / 120), toPiece.dot(right.setFromMatrixColumn(camera.matrixWorld, 0)) / Math.max(far, 1));
          }
        }
        if (t !== m.last) {
          m.last = t;
          m.action.time = t * m.action.getClip().duration;
          m.mixer.update(0);
        }
        // (The flight's whole till it's fallen, its stump then.)
        if (m.asset === 'flight_collapse' && a.stump) a.stump.visible = t >= 1;
      }
    }
    if (b?.root.visible) {
      const open = doorOpen(2);
      if (b.door) b.door.rotation.y = -open * sections.bulkhead.openDeg * DEGREES;
      if (b.sealFar) b.sealFar.visible = !hallShown(u);
      const lit = doorState[2].lit;
      // Each win steps the wheel round a quarter, and lights a lamp; all lit, it swings.
      b.wheelAngle += (lit * WHEEL_STEP - b.wheelAngle) * Math.min(1, delta * WHEEL_RATE);
      if (b.wheel) b.wheel.rotation.x = b.wheelAngle % TAU;
      for (const [i, m] of b.lamps.entries()) {
        if (!m) continue;
        m.userData.off ??= { r: m.emissive.r, g: m.emissive.g, b: m.emissive.b, strength: m.emissiveIntensity };
        const off = m.userData.off as typeof LAMP_LIT;
        const on = i < lit ? LAMP_LIT : off;
        m.emissive.setRGB(on.r, on.g, on.b);
        m.emissiveIntensity = on.strength;
      }
    }
  });

  return <group ref={holder} />;
}
