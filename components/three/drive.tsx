'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import { BoxGeometry, Color, ConeGeometry, type Group, InstancedMesh, type Material, MeshStandardMaterial, Object3D, Quaternion, Vector3 } from 'three';
import { isLightDevice } from '@/lib/journey';
import { ride, road } from '@/lib/ride';
import { AT } from './bike';
import { DRACO_PATH } from './biome';
import { CITY_URL, WINDOW, WINDOW_WARM } from './city';

// The endless street the bike rides into: past the far end of the city's freeway deck, the road carries on in tiles that
// are recycled ahead of the bike as it goes, each with its slab and pier, barriers and rails both sides, a lamp, and
// towers set back either side (their facades lit by world position, so any size of box gets windows). Everything is one
// InstancedMesh per material: six draw calls however far it goes. Tiles are placed from a hash of their index, so the
// street doesn't change when it's revisited.

const DECK_Y = -11;
const GROUND_Y = -80;
const TILE = 24; // m of road per tile
const BEHIND = 60; // m of street kept behind the bike
const SLAB = { width: 11.8, depth: 1.2 };
const TOWERS_PER_SIDE = 2;
const GANTRY_EVERY = 12; // tiles

const hash = (a: number, b: number, c = 0) => {
  const h = Math.sin(a * 127.1 + b * 311.7 + c * 74.7) * 43758.5453;
  return h - Math.floor(h);
};

/** Box facades with windows from their world position (lib: components/three/city.tsx's facade, for instances). */
function instancedFacade() {
  const material = new MeshStandardMaterial({ color: new Color(0.025, 0.03, 0.028), roughness: 0.75 });
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uWindow = { value: WINDOW };
    shader.uniforms.uWarm = { value: WINDOW_WARM };
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vDriveWorld;\nvarying vec3 vDriveNormal;\nvarying vec2 vSeed;')
      .replace(
        '#include <worldpos_vertex>',
        `#include <worldpos_vertex>
mat4 driveModel = modelMatrix;
#ifdef USE_INSTANCING
driveModel = modelMatrix * instanceMatrix;
vSeed = instanceMatrix[3].xz;
#else
vSeed = vec2(0.0);
#endif
vDriveWorld = (driveModel * vec4(transformed, 1.0)).xyz;
vDriveNormal = mat3(driveModel) * objectNormal;`
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
uniform vec3 uWindow;
uniform vec3 uWarm;
varying vec3 vDriveWorld;
varying vec3 vDriveNormal;
varying vec2 vSeed;
float driveHash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }`
      )
      .replace(
        '#include <emissivemap_fragment>',
        `#include <emissivemap_fragment>
{
  vec3 n = normalize(vDriveNormal);
  if (abs(n.y) < 0.03) {
    // Metres along the wall and up from the ground; floors 2.8 m, bays 2.2 m.
    vec2 t = normalize(vec2(-n.z, n.x));
    vec2 wall = vec2(dot(vDriveWorld.xz, t), vDriveWorld.y - (${GROUND_Y.toFixed(1)}));
    vec2 cell = floor(wall / vec2(2.2, 2.8));
    vec2 f = fract(wall / vec2(2.2, 2.8));
    float building = floor(dot(vSeed, vec2(0.37, 0.61)));
    float h = driveHash(vec3(cell, building));
    float floorLit = step(0.45, driveHash(vec3(cell.y, building, 3.0)));
    float lit = step(0.62, h) * floorLit + step(0.93, h);
    float pane = step(0.22, f.x) * step(f.x, 0.78) * step(0.28, f.y) * step(f.y, 0.8);
    vec3 tint = mix(uWindow, uWarm, step(0.9, driveHash(vec3(cell, building + 5.0))));
    totalEmissiveRadiance += tint * pane * lit * (0.5 + 1.6 * driveHash(vec3(cell, 9.0)));
  }
}`
      );
  };
  material.customProgramCacheKey = () => 'drive-facade';
  return material;
}

type Parts = Record<'asphalt' | 'concrete' | 'steel' | 'lamps' | 'towers' | 'spikes', InstancedMesh>;

export function DriveStreet() {
  const { scene } = useGLTF(CITY_URL, DRACO_PATH);
  const group = useRef<Group>(null);
  const tiles = useMemo(() => Math.ceil((isLightDevice() ? 520 : 760) / TILE) + Math.ceil(BEHIND / TILE), []);

  // The road: the deck marker's centre line, heading and far end (the end the bike faces).
  useMemo(() => {
    const top = scene.getObjectByName('CityDeckTop') ?? scene.getObjectByName('City.DeckTop');
    if (!top) return;
    scene.updateMatrixWorld(true);
    const centre = top.getWorldPosition(new Vector3());
    const along = new Vector3(1, 0, 0).applyQuaternion(top.getWorldQuaternion(new Quaternion())).setY(0).normalize();
    const { length = 660, width = 9.25 } = top.userData as { length?: number; width?: number };
    const bike = new Vector3(...AT);
    // (The bike faces whichever end is nearer its nose: the deck's -x end, in practice.)
    const offset = bike.clone().sub(centre).dot(along);
    const ahead = offset < 0 ? along.clone().negate() : along.clone();
    road.ahead.copy(ahead);
    road.yaw = Math.atan2(-ahead.z, ahead.x);
    road.end = length / 2 - Math.abs(offset);
    road.endCentre
      .copy(centre)
      .addScaledVector(ahead, length / 2)
      .setY(DECK_Y);
    road.width = width + 2.55;
    road.known = true;
  }, [scene]);

  const parts = useMemo<Parts>(() => {
    const box = new BoxGeometry(1, 1, 1).translate(0, 0.5, 0);
    const cone = new ConeGeometry(0.5, 1, 4).translate(0, 0.5, 0);
    const make = (geometry: BoxGeometry | ConeGeometry, material: Material, count: number, name: string) => {
      const mesh = new InstancedMesh(geometry, material, count);
      mesh.name = name;
      mesh.count = 0;
      // (Their bounds would be the unit box: they span the street, so they're never culled as a whole.)
      mesh.frustumCulled = false;
      return mesh;
    };
    return {
      asphalt: make(box, new MeshStandardMaterial({ color: new Color(0.035, 0.04, 0.037), roughness: 0.32, metalness: 0.1 }), tiles, 'DriveAsphalt'),
      concrete: make(box, new MeshStandardMaterial({ color: new Color(0.05, 0.055, 0.052), roughness: 0.9 }), tiles * 3 + 8, 'DriveConcrete'),
      steel: make(box, new MeshStandardMaterial({ color: new Color(0.08, 0.085, 0.08), roughness: 0.4, metalness: 0.85 }), tiles * 3 + 8, 'DriveSteel'),
      lamps: make(
        box,
        new MeshStandardMaterial({ color: new Color(0.8, 1, 0.7), emissive: new Color(0.75, 1, 0.55), emissiveIntensity: 7, toneMapped: false }),
        tiles,
        'DriveLamps'
      ),
      towers: make(box, instancedFacade(), tiles * TOWERS_PER_SIDE * 2 * 2, 'DriveTowers'),
      spikes: make(cone, new MeshStandardMaterial({ color: new Color(0.02, 0.025, 0.022), roughness: 0.7 }), tiles * TOWERS_PER_SIDE * 2, 'DriveSpikes'),
    };
  }, [tiles]);
  useEffect(
    () => () => {
      for (const m of Object.values(parts)) {
        (m.material as Material).dispose();
        m.dispose();
      }
    },
    [parts]
  );

  const last = useRef(Number.NaN);
  const o = useMemo(() => new Object3D(), []);
  const at = useMemo(() => new Vector3(), []);
  const side = useMemo(() => new Vector3(), []);

  useFrame(() => {
    const g = group.current;
    if (!g) return;
    // Only once on the bike: it's out of the landing's view, and costs nothing until then.
    g.visible = road.known && (ride.mount > 0.01 || ride.drive.s > 0);
    if (!g.visible) return;
    // Rebuild the instances whenever the first tile in range changes (every TILE metres of riding).
    const past = ride.drive.s - road.end;
    const first = Math.max(0, Math.floor((past - BEHIND) / TILE));
    if (first === last.current) return;
    last.current = first;

    side.set(-road.ahead.z, 0, road.ahead.x);
    const counts: Record<keyof Parts, number> = { asphalt: 0, concrete: 0, steel: 0, lamps: 0, towers: 0, spikes: 0 };
    const put = (part: keyof Parts, along: number, across: number, y: number, sx: number, sy: number, sz: number, turn = 0) => {
      at.copy(road.endCentre).addScaledVector(road.ahead, along).addScaledVector(side, across);
      o.position.set(at.x, y, at.z);
      o.rotation.set(0, road.yaw + turn, 0);
      o.scale.set(sx, sy, sz);
      o.updateMatrix();
      parts[part].setMatrixAt(counts[part]++, o.matrix);
    };

    const half = SLAB.width / 2;
    for (let k = first; k < first + tiles; k++) {
      const a = (k + 0.5) * TILE;
      // The slab (a hair longer than its tile, so there's no seam), its pier, the jersey barriers and rails.
      put('asphalt', a, 0, DECK_Y - SLAB.depth, TILE + 0.05, SLAB.depth, SLAB.width);
      put('concrete', a, 0, GROUND_Y, 2.4, DECK_Y - SLAB.depth - GROUND_Y, 2.4);
      for (const s of [-1, 1]) {
        put('concrete', a, s * (half - 0.25), DECK_Y, TILE + 0.05, 0.9, 0.5);
        put('steel', a, s * (half - 0.25), DECK_Y + 1.1, TILE + 0.05, 0.12, 0.08);
      }
      // A lamp post, alternating sides, its head leaning out over the road.
      const ls = k % 2 ? 1 : -1;
      put('steel', a, ls * (half - 0.25), DECK_Y + 0.9, 0.18, 7, 0.18);
      put('lamps', a, ls * (half - 1.1), DECK_Y + 7.8, 0.5, 0.22, 1.6);
      // Now and then a gantry over the road.
      if (k % GANTRY_EVERY === 5) {
        for (const s of [-1, 1]) put('concrete', a, s * (half + 0.6), DECK_Y, 0.7, 7.5, 0.7);
        put('steel', a, 0, DECK_Y + 6.6, 1.2, 0.9, SLAB.width + 2.4);
      }
      // Towers either side, set back off the road, rising from the city floor: a body and a setback crown, some with a
      // spire on top.
      for (const s of [-1, 1]) {
        for (let j = 0; j < TOWERS_PER_SIDE; j++) {
          const r = (n: number) => hash(k, s * 7 + j, n);
          const across = s * (half + 22 + r(1) * 90);
          const along = (k + r(2)) * TILE;
          const w = 9 + r(3) * 16;
          const d = 9 + r(4) * 16;
          const h = 70 + r(5) ** 1.5 * 190;
          const turn = (r(6) - 0.5) * 0.2;
          const body = h * (0.62 + r(7) * 0.2);
          put('towers', along, across, GROUND_Y, w, body, d, turn);
          put('towers', along, across, GROUND_Y + body, w * 0.68, h - body, d * 0.68, turn);
          if (r(8) > 0.45) put('spikes', along, across, GROUND_Y + h, w * 0.5, 12 + r(9) * 40, d * 0.5, turn + Math.PI / 4);
        }
      }
    }
    for (const key of Object.keys(parts) as (keyof Parts)[]) {
      parts[key].count = counts[key];
      parts[key].instanceMatrix.needsUpdate = true;
    }
  });

  return (
    <group ref={group} visible={false}>
      {Object.values(parts).map((mesh) => (
        <primitive key={mesh.name} object={mesh} />
      ))}
    </group>
  );
}

if (typeof window !== 'undefined') useGLTF.preload(CITY_URL, DRACO_PATH);
