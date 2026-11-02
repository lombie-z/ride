'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { type Group, InstancedMesh, type Material, Matrix4, type Mesh, Mesh as MeshClass, type MeshStandardMaterial, type Texture, Vector3 } from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { ride, road, setCityPath } from '@/lib/ride';
import { AT, sunsetEnvMap } from './bike';
import { DRACO_PATH } from './biome';
import { Muck } from './muck';
import { Traffic } from './traffic';
import { useVoidGloop, voidGloop } from './void-gloop';
import { CityRoadMirror } from './wet-road';

// The second city (art/build-city2.py), loaded during the ride: it's downloaded once the visitor gets on the bike,
// its shaders compiled and textures uploaded off to the side, and only then marked ready, which is what sets the bike's
// chrome morph and the change of sky going (components/three/ride.tsx), which places it down the road ahead, its own
// road taking over from the endless one (lib/ride.ts cityRoadAt).
// (Dev: ?city2=<url> loads another model in its place, to try the flow.)
const URL = '/models/city2.glb';
const url = () => (process.env.NODE_ENV === 'development' && new URLSearchParams(window.location.search).get('city2')) || URL;

function CityTwo({ src }: { src: string }) {
  const { scene } = useGLTF(src, DRACO_PATH);
  const group = useRef<Group>(null);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const world = useThree((s) => s.scene);
  useVoidGloop();
  // Its road's centreline, for the bike to follow (before anything that places itself along it renders).
  useMemo(() => {
    const marker = scene.getObjectByName('City2RoadPath') ?? scene.getObjectByName('City2.RoadPath');
    const d = marker?.userData as { points?: number[][]; step?: number; length?: number } | undefined;
    if (d?.points && d.length) setCityPath(d.points, d.step ?? 2, d.length);
  }, [scene]);

  // Its materials: the sunset in their reflections; the lit glass, lamps, screen and sun past white for the bloom; the
  // sun itself clear of the haze, far out.
  useEffect(() => {
    const env = sunsetEnvMap(gl);
    scene.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      const m = mesh.material as MeshStandardMaterial;
      m.envMap = env;
      m.envMapIntensity = 1.2;
      if (/^City2(Glass|GlassWarm|Lamp|Screen|Sun)$/.test(m.name)) {
        m.emissiveIntensity = m.name === 'City2Sun' ? 14 : m.name === 'City2Screen' ? 3 : 4;
        m.toneMapped = false;
      }
      if (m.name === 'City2Sun') m.fog = false;
      // The ooze (the billboard's drips, its puddles on the plaza) reflects nothing: it's a window onto somewhere else
      // (components/three/void-gloop.ts), like the slicks.
      if (m.name === 'City2Ooze') {
        mesh.material = voidGloop();
        return;
      }
      // The rounded pearl forms (terraces, platforms, the bubble pods round the plaza) are matte: chalky, not glossy.
      if (m.name === 'City2Pearl') {
        m.roughness = 0.82;
        m.metalness = 0;
        m.envMapIntensity = 0.12;
      }
      // (Glossy, not a mirror: the lamps' reflections sat on it as bright blobs.)
      if (m.name === 'City2Floor') m.roughness = Math.max(m.roughness, 0.22);
      m.needsUpdate = true;
    });
  }, [scene, gl]);

  // Drawn in as few calls as it can be: its static meshes merged into one per material, and its instanced pieces (the
  // glb's GPU instancing, one per node) gathered into one instanced mesh per geometry and material. (After its
  // materials are set: the ooze has been swapped for its own.)
  useEffect(() => {
    scene.updateMatrixWorld(true);
    const toScene = new Matrix4().copy(scene.matrixWorld).invert();
    // (In cells of the city, so each merged piece covers only its part of it and the ones out of view aren't drawn.)
    const CELL = 260;
    const cellOf = (x: number, z: number) => `${Math.floor(x / CELL)},${Math.floor(z / CELL)}`;
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
          const key = `${im.geometry.uuid}|${material.uuid}|${cellOf(centre.x, centre.z)}`;
          if (!instanced.has(key)) instanced.set(key, { source: im, matrices: [] });
          (instanced.get(key) as { matrices: Matrix4[] }).matrices.push(m);
        }
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
    gl.compileAsync(g, camera, world)
      .catch(() => {})
      .then(() => {
        if (!live) return;
        for (const t of textures) gl.initTexture(t);
        g.visible = false;
        ride.secondCity.ready = true;
      });
    return () => {
      live = false;
      ride.secondCity.ready = false;
    };
  }, [scene, gl, camera, world]);

  // Placed where the ride's change begins, turned to run on from the endless road (local +x along it).
  useFrame(() => {
    const g = group.current;
    const tr = ride.transition;
    if (!g || !ride.secondCity.ready) return;
    g.visible = tr.placed;
    if (!tr.placed) return;
    g.position.set(AT[0], AT[1], AT[2]).addScaledVector(road.ahead, tr.at);
    g.rotation.set(0, road.yaw, 0);
  });

  return (
    <group ref={group} visible={false}>
      <primitive object={scene} />
      <Muck />
      <CityRoadMirror />
      <Traffic env={sunsetEnvMap(gl)} />
    </group>
  );
}

/** Starts loading the second city once the visitor's on the bike (if it's been built: the file's checked for first). */
export function CityTwoLoader() {
  const [src, setSrc] = useState<string | null>(null);
  const asked = useRef(false);
  useFrame(() => {
    if (asked.current || ride.mount < 0.5) return;
    asked.current = true;
    const target = url();
    fetch(target, { method: 'HEAD' })
      .then((r) => r.ok && setSrc(target))
      .catch(() => {});
  });
  return src ? (
    <Suspense fallback={null}>
      <CityTwo src={src} />
    </Suspense>
  ) : null;
}
