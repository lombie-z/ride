'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  type Group,
  InstancedMesh,
  type Material,
  Matrix4,
  type Mesh,
  Mesh as MeshClass,
  type MeshStandardMaterial,
  type Object3D,
  type Texture,
  Vector3,
} from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { course, type Shot, ZONES } from '@/lib/course';
import { leftBehind, MUCKY, ride, setZonePaths } from '@/lib/ride';
import { sunsetEnvMap, zoneEnvMap } from './bike';
import { DRACO_PATH } from './biome';
import { Muck } from './muck';
import { precompile } from './precompile';
import { Traffic } from './traffic';
import { useVoidGloop, voidGloop } from './void-gloop';
import { CityRoadMirror } from './wet-road';

// The cities after the green one (art/build-city2.py and on; lib/course.ts ZONES), each loaded during the ride before
// it: downloaded, its shaders compiled and textures uploaded off to the side, and only then marked ready (the chrome
// city's readiness is what places it down the street ahead and sets the change of sky and the bike's morph going,
// components/three/ride.tsx). Each is placed on the course where its road takes over (lib/course.ts), its own road the
// ride's from there.
// (Dev: ?city2=<url> (or city3, city4) loads another model in its place, to try the flow.)
const url = (k: number) => {
  const own = ZONES[k].city as string;
  if (process.env.NODE_ENV !== 'development') return own;
  return new URLSearchParams(window.location.search).get(`city${k + 1}`) || own;
};

/** A node of the city's glb by its Blender name (the loader drops the dot: City2.RoadPath is City2RoadPath). */
const node = (scene: Object3D, name: string) => scene.getObjectByName(name.replace('.', '')) ?? scene.getObjectByName(name);

/** Its arrival shot, from its ArrivalCam (Blender's frame, z up, into three's: x, z, -y). */
function shotOf(scene: Object3D, prefix: string): Shot | null {
  const d = node(scene, `${prefix}.ArrivalCam`)?.userData as { EYE?: number[]; LOOK?: number[]; FOV?: number } | undefined;
  if (!d?.EYE || !d.LOOK || !d.FOV) return null;
  const three = (v: number[]): [number, number, number] => [v[0], v[2], -v[1]];
  return { eye: three(d.EYE), look: three(d.LOOK), fov: d.FOV };
}

// Lit materials, by their name's ending: past white for the bloom.
const GLOWS: Record<string, number> = { Glass: 4, GlassWarm: 4, Lamp: 4, Screen: 3, Sun: 14, Amber: 3.2, Heart: 4.5, Led: 4, Lightning: 0, Fluid: 3 };

function ZoneCity({ k, src }: { k: number; src: string }) {
  const { prefix } = ZONES[k];
  const { scene } = useGLTF(src, DRACO_PATH);
  const group = useRef<Group>(null);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const world = useThree((s) => s.scene);
  const parts = useRef<{ heart: Object3D | null; lightning: MeshStandardMaterial[] }>({ heart: null, lightning: [] });
  useVoidGloop();
  // Its road's centreline in and on out, for the bike to follow (before anything that places itself along it renders),
  // where its way out ends (the next zone carries on from there), and its arrival shot.
  useMemo(() => {
    type Road = { points?: number[][]; step?: number; length?: number; END?: number[]; END_HEADING?: number };
    const road = (name: string) => {
      const d = node(scene, `${prefix}.${name}`)?.userData as Road | undefined;
      return d?.points && d.length ? (d as Required<Road>) : undefined;
    };
    const into = road('RoadPath');
    const out = road('RoadOut');
    setZonePaths(k, { in: into, out });
    const leg = course.legs[k];
    leg.end = out?.END ? { x: out.END[0], y: out.END[1], heading: out.END_HEADING ?? 0 } : null;
    leg.shot = shotOf(scene, prefix);
    // (Where its sun stands, for the sky's sun and the light to come from there.)
    scene.updateMatrixWorld(true);
    scene.traverse((o) => {
      const m = (o as Mesh).material as Material | undefined;
      if (!(o as Mesh).isMesh || m?.name !== `${prefix}Sun`) return;
      // (Its light's own direction where the city gives one, Blender's frame: a sun seen kilometres off over the
      // horizon can still be a noon sun overhead.)
      const own = (o.userData.SUN_LIGHT_DIR ?? o.parent?.userData.SUN_LIGHT_DIR) as number[] | undefined;
      if (own) {
        leg.sun = new Vector3(own[0], own[2], -own[1]).normalize();
        return;
      }
      const g = (o as Mesh).geometry;
      if (!g.boundingSphere) g.computeBoundingSphere();
      leg.sun = (g.boundingSphere as { center: Vector3 }).center.clone().applyMatrix4(o.matrixWorld).normalize();
    });
  }, [scene, k, prefix]);

  // Its materials: the sunset in their reflections; the lit glass, lamps, screens and sun past white for the bloom; the
  // sun itself clear of the haze, far out.
  useEffect(() => {
    const env = zoneEnvMap(gl, k);
    scene.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      const m = mesh.material as MeshStandardMaterial;
      m.envMap = env;
      m.envMapIntensity = 1.2;
      const kind = m.name.startsWith(prefix) ? m.name.slice(prefix.length) : m.name;
      if (kind in GLOWS) {
        m.emissiveIntensity = GLOWS[kind];
        m.toneMapped = false;
      }
      if (kind === 'Sun') m.fog = false;
      // The ooze (the drips, its puddles) reflects nothing: it's a window onto somewhere else
      // (components/three/void-gloop.ts), like the slicks.
      if (kind === 'Ooze') {
        mesh.material = voidGloop();
        return;
      }
      // The rounded pearl forms (terraces, platforms, the bubble pods round the plaza) are matte: chalky, not glossy;
      // the hive's bone, the same.
      if (kind === 'Pearl' || kind === 'Bone') {
        m.roughness = 0.82;
        m.metalness = 0;
        m.envMapIntensity = kind === 'Bone' ? 0.25 : 0.12;
      }
      // (Glossy, not a mirror: the lamps' reflections sat on it as bright blobs.)
      if (kind === 'Floor') m.roughness = Math.max(m.roughness, 0.22);
      // The hive's polished stone: a sheen of the dawn sky.
      if (kind === 'Stone') {
        m.roughness = Math.min(Math.max(m.roughness, 0.12), 0.2);
        m.envMapIntensity = 1.5;
      }
      // The sandstorm's billboards and the hive's mist sheets: soft, unlit by the sun's glints, never writing depth.
      if (kind === 'Storm' || kind === 'Mist' || kind === 'Haze') {
        m.depthWrite = false;
        m.envMapIntensity = 0;
      }
      m.needsUpdate = true;
    });
    // The hive's heart, beating (components/three/ride.tsx: the heartbeat), and the desert's lightning.
    // (Found by its material: its name's shared with the ooze it hangs under.)
    parts.current = { heart: null, lightning: [] as MeshStandardMaterial[] };
    scene.traverse((o) => {
      const m = (o as Mesh).material as MeshStandardMaterial | undefined;
      if (m?.name === `${prefix}Heart`) parts.current.heart = o;
      if (m?.name === `${prefix}Lightning` && !parts.current.lightning.includes(m)) parts.current.lightning.push(m);
    });
  }, [scene, gl, prefix, k]);

  // Drawn in as few calls as it can be: its static meshes merged into one per material, and its instanced pieces (the
  // glb's GPU instancing, one per node) gathered into one instanced mesh per geometry and material. (After its
  // materials are set: the ooze has been swapped for its own.)
  useEffect(() => {
    scene.updateMatrixWorld(true);
    const toScene = new Matrix4().copy(scene.matrixWorld).invert();
    // (In cells of the city, so each merged piece covers only its part of it and the ones out of view aren't drawn.)
    const CELL = 260;
    const cellOf = (x: number, z: number) => `${Math.floor(x / CELL)},${Math.floor(z / CELL)}`;
    // (Instanced pieces in cells twice as wide: they're cheap to draw out of view, and each cell's another call.)
    const wideCellOf = (x: number, z: number) => `${Math.floor(x / (2 * CELL))},${Math.floor(z / (2 * CELL))}`;
    const centre = new Vector3();
    const plain = new Map<string, Mesh[]>();
    const instanced = new Map<string, { source: InstancedMesh; matrices: Matrix4[] }>();
    const each = new Matrix4();
    const sources: Mesh[] = [];
    scene.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh || Array.isArray(mesh.material)) return;
      sources.push(mesh);
    });
    for (const mesh of sources) {
      const material = mesh.material as Material;
      if ((mesh as InstancedMesh).isInstancedMesh) {
        const im = mesh as InstancedMesh;
        const base = toScene.clone().multiply(im.matrixWorld);
        for (let k = 0; k < im.count; k++) {
          im.getMatrixAt(k, each);
          const m = base.clone().multiply(each);
          centre.setFromMatrixPosition(m);
          const key = `${im.geometry.uuid}|${material.uuid}|${wideCellOf(centre.x, centre.z)}`;
          if (!instanced.has(key)) instanced.set(key, { source: im, matrices: [] });
          (instanced.get(key) as { matrices: Matrix4[] }).matrices.push(m);
        }
        // (Anything hung under it, kept where it is: the hive's heart hangs under its ooze.)
        for (const child of [...im.children]) (im.parent ?? scene).attach(child);
        im.removeFromParent();
        continue;
      }
      const g = mesh.geometry;
      if (!g.boundingBox) g.computeBoundingBox();
      g.boundingBox?.getCenter(centre);
      centre.applyMatrix4(toScene.clone().multiply(mesh.matrixWorld));
      const key = `${material.uuid}|${Object.keys(g.attributes).sort().join()}|${!!g.index}|${cellOf(centre.x, centre.z)}`;
      plain.set(key, [...(plain.get(key) ?? []), mesh]);
    }
    const place = (o: Mesh, from: Mesh) => {
      o.castShadow = from.castShadow;
      o.receiveShadow = from.receiveShadow;
      o.renderOrder = from.renderOrder;
      scene.add(o);
    };
    for (const meshes of plain.values()) {
      if (meshes.length < 2) continue;
      const merged = mergeGeometries(meshes.map((m) => m.geometry.clone().applyMatrix4(toScene.clone().multiply(m.matrixWorld))));
      if (!merged) continue;
      const one = new MeshClass(merged, meshes[0].material);
      one.name = `${(meshes[0].material as Material).name}Merged`;
      place(one, meshes[0]);
      for (const m of meshes) m.removeFromParent();
    }
    for (const { source, matrices } of instanced.values()) {
      const one = new InstancedMesh(source.geometry, source.material, matrices.length);
      one.name = `${(source.material as Material).name}Instances`;
      for (const [i, m] of matrices.entries()) one.setMatrixAt(i, m);
      one.computeBoundingSphere();
      place(one, source);
    }
  }, [scene]);

  useEffect(() => {
    let live = true;
    const g = group.current;
    if (!g) return;
    // Compile its programs against the real scene's lights, in the background, then upload its textures; drawn
    // nowhere yet.
    g.visible = true;
    const textures = new Set<Texture>();
    scene.traverse((o) => {
      const m = (o as Mesh).material as (Material & Record<string, unknown>) | undefined;
      for (const v of Object.values(m ?? {})) if ((v as Texture)?.isTexture) textures.add(v as Texture);
    });
    precompile(gl, g, camera, world)
      .catch(() => {})
      .then(() => {
        if (!live) return;
        for (const t of textures) gl.initTexture(t);
        g.visible = false;
        course.legs[k].ready = true;
      });
    return () => {
      live = false;
      course.legs[k].ready = false;
    };
  }, [scene, gl, camera, world, k]);

  // Placed where its road takes over on the course, turned to run on from the road before (local +x along it); drawn
  // while it's the zone the ride's heading for or the one it's just left.
  const flash = useRef({ next: 3, at: -1 });
  useFrame((state) => {
    const g = group.current;
    const leg = course.legs[k];
    if (!g || !leg.ready) return;
    g.visible = leg.placed && (k === ride.zone || k === ride.zone - 1) && !leftBehind(k);
    if (!g.visible) return;
    g.position.copy(leg.origin);
    g.rotation.set(0, leg.yaw, 0);
    const { heart, lightning } = parts.current;
    // (Relative to its own scale: it's modelled as a unit sphere, scaled up.)
    if (heart) {
      if (!heart.userData.size) heart.userData.size = heart.scale.clone();
      heart.scale.copy(heart.userData.size).multiplyScalar(1 + 0.06 * ride.drive.beat);
    }
    // (Now and then a fork of lightning in the storm: a quick double flicker.)
    if (lightning.length) {
      const t = state.clock.elapsedTime;
      const f = flash.current;
      if (t > f.next) {
        f.at = t;
        f.next = t + 2.5 + Math.random() * 6;
      }
      const since = t - f.at;
      const on = since < 0.08 || (since > 0.16 && since < 0.24) ? 1 : 0;
      for (const m of lightning) {
        m.emissiveIntensity = 12 * on;
        m.toneMapped = false;
      }
    }
  });

  return (
    <group ref={group} visible={false}>
      <primitive object={scene} />
      {MUCKY[k] && <Muck k={k} />}
      {MIRROR[k] > 0 && <CityRoadMirror k={k} strength={MIRROR[k]} />}
      {k === 1 && <Traffic env={sunsetEnvMap(gl)} />}
    </group>
  );
}

/**
 * How much of a mirror each city's road is: the chrome city's pure mirror. (Not the hive's: reflecting that dense city
 * a second time doubled the frame's cost, 6 to 23 ms; its polished stone catches the dawn from its environment instead.)
 */
const MIRROR = [0, 1, 0, 0];

/**
 * Starts loading a city when the ride's on its way toward the one before (the chrome city once the visitor's on the
 * bike), if it's been built: the file's checked for first.
 */
export function ZoneCityLoader({ k }: { k: number }) {
  const [src, setSrc] = useState<string | null>(null);
  const asked = useRef(false);
  useFrame(() => {
    if (asked.current || ride.mount < 0.5) return;
    if (k > 1 && !(ride.zone > k - 1 || (ride.zone === k - 1 && ride.transition.placed))) return;
    asked.current = true;
    const target = url(k);
    fetch(target, { method: 'HEAD' })
      .then((r) => r.ok && setSrc(target))
      .catch(() => {});
  });
  return src ? (
    <Suspense fallback={null}>
      <ZoneCity k={k} src={src} />
    </Suspense>
  ) : null;
}
