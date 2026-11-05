'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import {
  BoxGeometry,
  Color,
  ConeGeometry,
  type Group,
  InstancedBufferAttribute,
  InstancedMesh,
  type Material,
  MeshBasicMaterial,
  MeshStandardMaterial,
  Object3D,
  Quaternion,
  Vector3,
} from 'three';
import { course } from '@/lib/course';
import { isLightDevice } from '@/lib/journey';
import { ride, road } from '@/lib/ride';
import { type Branch, DECK_Y, FLYOVERS, flyoverY, GROUND_Y, HALF, type Hall, hash, type Over, ROOF, SLAB, TILE, tileAt, towerClear } from '@/lib/street';
import { AT } from './bike';
import { DRACO_PATH } from './biome';
import { CITY_URL, WINDOW, WINDOW_WARM } from './city';
import { StreetRiders } from './street-riders';
import { weathered } from './weathered';
import { RideMirror } from './wet-road';

// The endless street the bike rides into: past the far end of the city's freeway deck, the road carries on in tiles that
// are recycled ahead of the bike as it goes, each with its slab and pier, barriers and rails both sides, a lamp, and
// towers set back either side (their facades lit by world position, so any size of box gets windows). What else stands
// on a tile (side streets, overpasses, halls through towers, a canyon's walls) is lib/street.ts's plan, from the tile's
// index, so the street doesn't change when it's revisited. Everything is one InstancedMesh per material: a few draw
// calls however far it goes.

const BEHIND = 60; // m of street kept behind the bike
const TOWERS_PER_SIDE = 2;
const GANTRY_EVERY = 12; // tiles
// A side street's lights and the towers lining it, along its length (m).
const STREET_LAMP_EVERY = 24;
const STREET_TOWER_EVERY = 44;

const GREEN = new Color(0.5, 1, 0.5);
const WHITE = new Color(0.86, 1, 0.84);
const WARM = new Color(1, 0.78, 0.48);

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

type PartName = 'asphalt' | 'concrete' | 'steel' | 'lamps' | 'towers' | 'spikes' | 'pearl' | 'strip' | 'glow';
type Parts = Record<PartName, InstancedMesh>;

// Nearing the second city (from this far before its road begins, where its sunset has mostly come in) the street's
// railings turn to its kind: a rounded pearl kerb topped with a lit strip (art/build-city2.py City2.RoadKerb, RoadStrip),
// with no lamp posts or gantries; so the edge is one kind or the other, never both.
const CHROME_RAILS_BEFORE = 150;
// How far before the chrome city the towers by its side of the road sink away; and the left side's, close by.
const SINK_BEFORE = 380;
const SINK_LEFT_BEFORE = 170;

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
    const glow = make(box, new MeshBasicMaterial({ color: 0xffffff, toneMapped: false }), tiles * 30 + 120, 'DriveGlow');
    // (Each its own colour, past white where the bloom's to take it.)
    glow.instanceColor = new InstancedBufferAttribute(new Float32Array((tiles * 30 + 120) * 3), 3);
    return {
      asphalt: make(box, new MeshStandardMaterial({ color: new Color(0.035, 0.04, 0.037), roughness: 0.32, metalness: 0.1 }), tiles * 3, 'DriveAsphalt'),
      concrete: make(
        box,
        weathered(new MeshStandardMaterial({ color: new Color(0.09, 0.095, 0.09), roughness: 0.9 }), 'concrete'),
        tiles * 12 + 60,
        'DriveConcrete'
      ),
      steel: make(
        box,
        weathered(new MeshStandardMaterial({ color: new Color(0.1, 0.105, 0.1), roughness: 0.4, metalness: 0.85 }), 'steel'),
        tiles * 8 + 60,
        'DriveSteel'
      ),
      pearl: make(box, new MeshStandardMaterial({ color: new Color(0.93, 0.9, 0.96), roughness: 0.8, metalness: 0 }), tiles * 2, 'DrivePearlKerb'),
      strip: make(
        box,
        new MeshStandardMaterial({ color: new Color(1, 0.95, 0.9), emissive: new Color(1, 0.86, 0.72), emissiveIntensity: 5, toneMapped: false }),
        tiles * 2,
        'DriveKerbStrip'
      ),
      lamps: make(
        box,
        new MeshStandardMaterial({ color: new Color(0.8, 1, 0.7), emissive: new Color(0.75, 1, 0.55), emissiveIntensity: 7, toneMapped: false }),
        tiles * 3 + 40,
        'DriveLamps'
      ),
      towers: make(box, instancedFacade(), tiles * 24, 'DriveTowers'),
      spikes: make(cone, new MeshStandardMaterial({ color: new Color(0.02, 0.025, 0.022), roughness: 0.7 }), tiles * TOWERS_PER_SIDE * 3, 'DriveSpikes'),
      glow,
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

  // The instance writers, kept for the life of the street (they run every frame while the towers are sinking).
  const build = useMemo(() => {
    const o = new Object3D();
    const at = new Vector3();
    const side = new Vector3();
    const tint = new Color();
    const counts: Record<PartName, number> = { asphalt: 0, concrete: 0, steel: 0, lamps: 0, towers: 0, spikes: 0, pearl: 0, strip: 0, glow: 0 };
    const put = (part: PartName, along: number, across: number, y: number, sx: number, sy: number, sz: number, turn = 0, pitch = 0) => {
      const mesh = parts[part];
      if (counts[part] >= mesh.instanceMatrix.count) return -1;
      at.copy(road.endCentre).addScaledVector(road.ahead, along).addScaledVector(side, across);
      o.position.set(at.x, y, at.z);
      o.rotation.set(0, road.yaw + turn, pitch);
      o.scale.set(sx, sy, sz);
      o.updateMatrix();
      mesh.setMatrixAt(counts[part], o.matrix);
      return counts[part]++;
    };
    const glow = (along: number, across: number, y: number, sx: number, sy: number, sz: number, colour: Color, gain: number, turn = 0) => {
      const i = put('glow', along, across, y, sx, sy, sz, turn);
      if (i >= 0) parts.glow.setColorAt(i, tint.copy(colour).multiplyScalar(gain));
    };
    /** A jersey barrier and its rail, from one point along the road to another. */
    const barrier = (from: number, to: number, across: number) => {
      if (to <= from) return;
      put('concrete', (from + to) / 2, across, DECK_Y, to - from + 0.05, 0.9, 0.5);
      put('steel', (from + to) / 2, across, DECK_Y + 1.1, to - from + 0.05, 0.12, 0.08);
    };
    return { counts, put, glow, barrier, side };
  }, [parts]);

  const last = useRef(Number.NaN);
  const builtClear = useRef(0);
  const sinkTick = useRef(0);

  useFrame(() => {
    const g = group.current;
    if (!g) return;
    // Only once on the bike: it's out of the landing's view, and costs nothing until then.
    // (And gone once the ride's left the chrome city behind: it's kilometres back by then.)
    g.visible = road.known && (ride.mount > 0.01 || ride.drive.s > 0) && ride.zone <= 1;
    if (!g.visible) return;
    // Rebuild the instances whenever the first tile in range changes (every TILE metres of riding).
    const past = ride.drive.s - road.end;
    // On the bike, the street's barriers and rails also line the city's own deck back to the bike's spot (the deck
    // keeps only the landing shot's low kerb); from the landing they're left off, so the shot's unchanged.
    const seated = ride.mount > 0.5;
    const first = seated ? Math.floor(-road.end / TILE) - 1 : Math.max(0, Math.floor((past - BEHIND) / TILE));
    const from = Math.max(first, Math.floor((past - BEHIND) / TILE));
    const tr = ride.transition;
    const chrome = course.legs[1];
    const key = from * 4 + (seated ? 1 : 0) + (chrome.placed ? 2 : 0);
    // (Rebuilt while the towers by the water are sinking away: every third frame, it's a slow move and a full rebuild.)
    const stale = tr.clear !== builtClear.current;
    if (key === last.current && !(stale && (sinkTick.current++ % 3 === 0 || tr.clear >= 1))) return;
    last.current = key;
    builtClear.current = tr.clear;

    const { counts, put, glow, barrier, side } = build;
    side.set(-road.ahead.z, 0, road.ahead.x);
    for (const name of Object.keys(counts) as PartName[]) counts[name] = 0;

    const half = HALF;
    // Where the second city's road takes over (as a distance past the deck's end), once it's placed.
    const cityAt = chrome.placed ? chrome.at - road.end : Number.POSITIVE_INFINITY;
    const eased = tr.clear * tr.clear * (3 - 2 * tr.clear);
    // Nearing the second city, its side of the road (the right: across the water) opens up: the towers there sink away
    // into the haze below (eased) as the train's beam rises. (On the left, only those nearest its road.)
    const sinkAt = (along: number, s: number) => (along > cityAt - (s > 0 ? SINK_BEFORE : SINK_LEFT_BEFORE) ? eased : 0);

    for (let k = from; k < from + tiles; k++) {
      const a = (k + 0.5) * TILE;
      // The street ends where the second city's road begins.
      if ((k + 1) * TILE > cityAt) break;
      if (k < 0) {
        // Alongside the deck: barriers, rails and lamps only.
        for (const s of [-1, 1]) barrier(k * TILE, (k + 1) * TILE, s * (half - 0.25));
        const ds = k % 2 ? 1 : -1;
        put('steel', a, ds * (half - 0.25), DECK_Y + 0.9, 0.18, 7, 0.18);
        put('lamps', a, ds * (half - 1.1), DECK_Y + 7.8, 0.5, 0.22, 1.6);
        continue;
      }
      const tile = tileAt(k);
      // The slab (a hair longer than its tile, so there's no seam), its pier, the jersey barriers and rails.
      put('asphalt', a, 0, DECK_Y - SLAB.depth, TILE + 0.05, SLAB.depth, SLAB.width);
      put('concrete', a, 0, GROUND_Y, 2.4, DECK_Y - SLAB.depth - GROUND_Y, 2.4);
      if ((k + 1) * TILE > cityAt - CHROME_RAILS_BEFORE) {
        for (const s of [-1, 1]) {
          put('pearl', a, s * (half - 0.25), DECK_Y + 0.25, TILE + 0.05, 0.6, 0.5);
          put('strip', a, s * (half - 0.25), DECK_Y + 0.84, TILE + 0.05, 0.06, 0.52);
        }
      } else if (tile.hall) {
        // In a hall, a low kerb: the walls are its edge.
        for (const s of [-1, 1]) put('concrete', a, s * (half - 0.25), DECK_Y, TILE + 0.05, 0.35, 0.5);
        buildHall(tile.hall, k, a);
      } else {
        for (const s of [-1, 1]) {
          // Where a side street leaves there's a gap in the barrier: its mouth, with the barrier stopping either side.
          const mouth = tile.branches.find((b) => b.side === s);
          if (mouth) {
            const gap = mouth.width / 2 / mouth.sin + 0.3;
            barrier(k * TILE, mouth.at - gap, s * (half - 0.25));
            barrier(mouth.at + gap, (k + 1) * TILE, s * (half - 0.25));
          } else barrier(k * TILE, (k + 1) * TILE, s * (half - 0.25));
        }
        // A lamp post, alternating sides, its head leaning out over the road.
        const ls = k % 2 ? 1 : -1;
        if (!tile.branches.some((b) => b.side === ls)) {
          put('steel', a, ls * (half - 0.25), DECK_Y + 0.9, 0.18, 7, 0.18);
          put('lamps', a, ls * (half - 1.1), DECK_Y + 7.8, 0.5, 0.22, 1.6);
        }
        // Now and then a gantry over the road.
        if (k % GANTRY_EVERY === 5 && !tile.over && tile.phase !== 'canyon') {
          for (const s of [-1, 1]) put('concrete', a, s * (half + 0.6), DECK_Y, 0.7, 7.5, 0.7);
          put('steel', a, 0, DECK_Y + 6.6, 1.2, 0.9, SLAB.width + 2.4);
          // (Lit along its underside, so it's one more thing passing overhead.)
          glow(a, 0, DECK_Y + 6.5, 0.5, 0.1, SLAB.width - 1, WHITE, 5);
        }
      }
      if (tile.over && (k + 1) * TILE < cityAt - CHROME_RAILS_BEFORE) buildOver(tile.over);
      if (tile.phase === 'canyon') buildCanyon(k, tile.bridge);
      // Towers either side, set back off the road, rising from the city floor: a body and a setback crown, some with a
      // spire on top. Well back on the open stretch, for the sky; behind the walls in the canyon; none where a hall's
      // own tower stands, or in the way of a side street.
      const open = tile.phase === 'open';
      for (const s of [-1, 1]) {
        for (let j = 0; j < TOWERS_PER_SIDE; j++) {
          const r = (n: number) => hash(k, s * 7 + j, n);
          const back = open ? 58 + r(1) * 120 : tile.phase === 'canyon' ? 34 + r(1) * 80 : 22 + r(1) * 90;
          if (tile.hall && back < tile.hall.wide + 14) continue;
          const across = s * (half + back);
          const along = (k + r(2)) * TILE;
          const w = 9 + r(3) * 16;
          const d = 9 + r(4) * 16;
          if (!towerClear(k, along, across, Math.max(w, d) * 0.7)) continue;
          const h = open ? 44 + r(5) ** 1.8 * 130 : 70 + r(5) ** 1.5 * 190;
          const turn = (r(6) - 0.5) * 0.2;
          const body = h * (0.62 + r(7) * 0.2);
          const sink = sinkAt(along, s);
          if (sink >= 1) continue;
          const down = sink * (h + 60);
          put('towers', along, across, GROUND_Y - down, w, body, d, turn);
          put('towers', along, across, GROUND_Y + body - down, w * 0.68, h - body, d * 0.68, turn);
          if (r(8) > 0.45) put('spikes', along, across, GROUND_Y + h - down, w * 0.5, 12 + r(9) * 40, d * 0.5, turn + Math.PI / 4);
        }
      }
    }
    // A side street can reach forward past the bike long after its mouth has gone by: so from further back than the road.
    for (let k = Math.max(0, from - 13); k < from + tiles; k++) {
      if ((k + 1) * TILE > cityAt - CHROME_RAILS_BEFORE) break;
      for (const b of tileAt(k).branches) buildBranch(b);
    }
    for (const f of FLYOVERS) {
      for (let x = Math.max(f.from, from); x < f.to && x < from + tiles; x++) buildFlyover(f, x);
    }
    for (const key of Object.keys(parts) as PartName[]) {
      parts[key].count = counts[key];
      // (None of a part in range, no draw call for it.)
      parts[key].visible = counts[key] > 0;
      // (Only the part in use goes up to the GPU: most of each buffer's spare, kept for the busiest stretches.)
      parts[key].instanceMatrix.addUpdateRange(0, counts[key] * 16);
      parts[key].instanceMatrix.needsUpdate = true;
    }
    if (parts.glow.instanceColor) {
      parts.glow.instanceColor.addUpdateRange(0, counts.glow * 3);
      parts.glow.instanceColor.needsUpdate = true;
    }

    /** A side street: its slab, barriers and lamps running off the road, and the towers lining it. */
    function buildBranch(b: Branch) {
      const { cos, sin, side: s, length, width } = b;
      const point = (on: number, off: number) => [b.at + on * cos - off * sin, s * (half + on * sin + off * cos)] as const;
      const turn = -s * b.angle;
      const [ma, mc] = point(length / 2 - 3, 0);
      put('asphalt', ma, mc, DECK_Y - SLAB.depth - 0.01, length + 6, SLAB.depth, width, turn);
      for (const e of [-1, 1]) {
        const off = (e * width) / 2;
        // (Each edge starts where it meets the road's barrier.)
        const start = Math.max(0, (-off * cos) / sin);
        const [ba, bc] = point((start + length) / 2, off);
        put('concrete', ba, bc, DECK_Y, length - start, 0.9, 0.5, turn);
        put('steel', ba, bc, DECK_Y + 1.1, length - start, 0.12, 0.08, turn);
      }
      // A kerb light along each edge, so a street reads a long way down it in the dark.
      for (const e of [-1, 1]) {
        const [la, lc] = point(length / 2, (e * (width - 1.4)) / 2);
        glow(la, lc, DECK_Y + 0.03, length, 0.05, 0.1, GREEN, 1.2, turn);
      }
      // A lit frame at its mouth, as at a hall's doorway; then lights strung across it, stacking away down the street.
      const [fa, fc] = point(5, 0);
      glow(fa, fc, DECK_Y + 7.6, 0.2, 0.3, width, GREEN, 9, turn);
      for (const e of [-1, 1]) {
        const [ja, jc] = point(5, (e * width) / 2);
        glow(ja, jc, DECK_Y, 0.2, 7.6, 0.3, GREEN, 9, turn);
      }
      for (let on = 28, i = 0; on < length; on += STREET_LAMP_EVERY, i++) {
        for (const e of [-1, 1]) {
          const [pa, pc] = point(on, (e * width) / 2);
          put('steel', pa, pc, DECK_Y + 0.9, 0.18, 6.6, 0.18, turn);
        }
        const [ha, hc] = point(on, 0);
        glow(ha, hc, DECK_Y + 7.4, 0.5, 0.14, width - 0.4, i % 3 === 2 ? GREEN : WHITE, 6.5, turn);
        // (Its pool on the road: flat, dim, but it's all the dry side street has to show it's there.)
        glow(ha, hc, DECK_Y + 0.02, 16, 0.02, width - 2, GREEN, 0.02, turn);
      }
      const sink = sinkAt(b.at, s);
      for (let on = 30, i = 0; on < length; on += STREET_TOWER_EVERY, i++) {
        for (const e of [-1, 1]) {
          const r = (n: number) => hash(b.k + i * 0.37, s * 3 + e, n);
          const d = 12 + r(1) * 12;
          const off = e * (width / 2 + 6 + d / 2 + r(2) * 8);
          const [ta, tc] = point(on, off);
          // (Not on the road: the near side of a street leaving at an angle stays clear of it for a while.)
          if (Math.abs(tc) < half + d) continue;
          const h = 60 + r(3) ** 1.4 * 170;
          put('towers', ta, tc, GROUND_Y - sink * (h + 60), 18 + r(4) * 12, h, d, turn);
        }
      }
    }

    /** An overpass across the road: its deck on two piers, lit along both edges and underneath. */
    function buildOver(v: Over) {
      const n = [Math.sin(v.turn), Math.cos(v.turn)] as const;
      put('concrete', v.at, 0, v.y - 1, v.span, 1, v.width, v.turn);
      for (const e of [-1, 1]) {
        put(
          'concrete',
          v.at - e * (half + 1.6) * Math.cos(v.turn) * -1,
          e * (half + 1.6) * Math.sin(v.turn) * -1,
          GROUND_Y,
          1.8,
          v.y - 1 - GROUND_Y,
          1.8,
          v.turn
        );
        const ea = v.at + (n[0] * e * v.width) / 2;
        const ec = (n[1] * e * v.width) / 2;
        glow(ea, ec, v.y - 0.55, v.span, 0.16, 0.16, GREEN, 5, v.turn);
        put('steel', ea, ec, v.y + 0.7, v.span, 0.1, 0.08, v.turn);
      }
      // (Strip lights under it, over the road.)
      for (const e of [-1, 0, 1]) glow(v.at + n[0] * e * 2.6, n[1] * e * 2.6, v.y - 1.1, 12, 0.08, 0.5, WHITE, 6, v.turn);
    }

    /** One tile of a tower the road runs through: its two sides, the floors over the road, and its lit ground floor. */
    function buildHall(hall: Hall, k: number, a: number) {
      const wall = half + 0.4;
      for (const s of [-1, 1]) put('towers', a, s * (wall + hall.wide / 2), GROUND_Y, TILE + 0.05, hall.tall, hall.wide);
      put('towers', a, 0, DECK_Y + ROOF, TILE + 0.05, hall.tall + GROUND_Y - DECK_Y - ROOF, wall * 2 + 0.1);
      // The doorway seen coming up to it: a lit frame round the hole in the tower's face.
      if (hall.i === 0) {
        const front = k * TILE - 0.1;
        glow(front, 0, DECK_Y + ROOF - 0.32, 0.2, 0.32, wall * 2, GREEN, 9);
        for (const s of [-1, 1]) glow(front, s * (wall - 0.15), DECK_Y, 0.2, ROOF, 0.3, GREEN, 9);
      }
      const bright = hall.kind !== 1;
      for (let i = 0; i < 6; i++) {
        const at = k * TILE + (i + 0.5) * 4;
        const r = (n: number) => hash(k, i, n + 30);
        if (bright) {
          // Strip lights across the ceiling (the bright kind in a full grid of panels), rushing by overhead.
          if (hall.kind === 0) glow(at, 0, DECK_Y + ROOF - 0.14, 0.55, 0.12, wall * 2 - 2.5, WHITE, 5.5);
          else for (const c of [-3.6, 0, 3.6]) glow(at, c, DECK_Y + ROOF - 0.14, 3, 0.12, 2.6, WHITE, 2.3);
          // Lit shopfronts along both walls, a few dark, a few warm: a big pane and a thin one over it, each its own width.
          for (const s of [-1, 1]) {
            const q = hash(k, i * s, 37);
            if (q < 0.14) continue;
            const colour = q > 0.86 ? WARM : q > 0.5 ? GREEN : WHITE;
            const gain = hall.kind === 2 ? 1.5 : 0.7 + r(3) * 0.7;
            glow(at, s * (wall - 0.05), DECK_Y + 1.1, 1.8 + r(1) * 1.6, 1.9 + r(2) * 0.9, 0.1, colour, gain);
            if (r(4) > 0.3)
              glow(at + (r(5) - 0.5) * 1.2, s * (wall - 0.05), DECK_Y + 3.6 + r(6) * 0.5, 1.2 + r(7) * 2.2, 0.5 + r(8) * 0.6, 0.1, colour, gain * 1.5);
          }
        } else {
          // The dim kind: columns along the walls, the dark between them; only its long lines of green.
          if (i % 2 === 0) for (const s of [-1, 1]) put('concrete', at, s * (wall - 0.5), DECK_Y, 1, ROOF, 1);
        }
      }
      if (!bright) {
        for (const c of [-3, 3]) glow(a, c, DECK_Y + ROOF - 0.12, TILE + 0.05, 0.1, 0.34, GREEN, 8);
        for (const s of [-1, 1]) glow(a, s * (half - 0.25), DECK_Y + 0.37, TILE + 0.05, 0.05, 0.08, GREEN, 2.4);
      }
    }

    /** The canyon's walls: towers hard up against the road, neon on their faces, a sky bridge now and then. */
    function buildCanyon(k: number, bridge: number) {
      for (const s of [-1, 1]) {
        for (let j = 0; j < 2; j++) {
          const r = (n: number) => hash(k, s * 5 + j * 11, n + 40);
          const along = k * TILE + (j + 0.5) * (TILE / 2);
          const sink = sinkAt(along, s);
          if (sink >= 1) continue;
          const d = 12 + r(1) * 14;
          const face = half + 1.2 + r(2) * 3.5;
          const across = s * (face + d / 2);
          // (A narrow slot between some of them, looking out.)
          const w = r(3) > 0.84 ? TILE / 2 - 7 : TILE / 2 + 0.05;
          const h = 90 + r(4) ** 1.2 * 210;
          const body = h * (0.7 + r(5) * 0.15);
          const down = sink * (h + 60);
          put('towers', along, across, GROUND_Y - down, w, body, d);
          put('towers', along, across, GROUND_Y + body - down, w * 0.7, h - body, d * 0.7);
          if (r(6) > 0.6) put('spikes', along, across, GROUND_Y + h - down, w * 0.45, 14 + r(7) * 36, d * 0.45, Math.PI / 4);
          // Neon: tall tubes up the wall, or a long band of sign at the height of the lamps.
          const on = s * (face - 0.1);
          const colour = r(8) > 0.84 ? WARM : r(8) > 0.4 ? GREEN : WHITE;
          if (r(9) > 0.45) glow(along + (r(10) - 0.5) * 6, on, DECK_Y + 2.5 + r(11) * 14 - down, 0.34, 10 + r(12) * 34, 0.16, colour, 8);
          else glow(along, on, DECK_Y + 5 + r(11) * 7 - down, w * 0.8, 0.8 + r(12) * 1.2, 0.14, colour, 3.2);
        }
      }
      if (bridge > 0) {
        const along = (k + 0.5) * TILE;
        // (Drawing back to the left wall as the right one sinks.)
        const reach = half + 3;
        const sink = sinkAt(along, 1);
        const right = reach - sink * reach * 2;
        const centre = (right - reach) / 2;
        const span = right + reach;
        if (span > 0.1) {
          put('concrete', along, centre, DECK_Y + bridge, 5, 3.4, span);
          glow(along - 2.54, centre, DECK_Y + bridge + 1.1, 0.1, 1.1, span, GREEN, 3.4);
          glow(along, centre, DECK_Y + bridge - 0.1, 3, 0.1, span, WHITE, 4);
        }
      }
    }

    /** One tile of a flyover: deck, pier, a lit edge. */
    function buildFlyover(f: (typeof FLYOVERS)[number], x: number) {
      const y0 = flyoverY(f, x);
      const y1 = flyoverY(f, x + 1);
      const along = (x + 0.5) * TILE;
      const pitch = Math.atan2(y1 - y0, TILE);
      const length = Math.hypot(TILE, y1 - y0) + 0.05;
      const mid = (y0 + y1) / 2;
      put('asphalt', along, f.across, mid - 1, length, 1, f.width, 0, pitch);
      put('concrete', along, f.across, GROUND_Y, 2, mid - 1 - GROUND_Y, 2);
      // (Lit along the edge nearest the road: it's what's seen of it from below.)
      const near = f.across > 0 ? f.across - f.width / 2 : f.across + f.width / 2;
      const far = f.across > 0 ? f.across + f.width / 2 : f.across - f.width / 2;
      glow(along, near, mid + 0.25, length, 0.14, 0.14, GREEN, 6, 0);
      put('steel', along, near, mid + 0.8, length, 0.08, 0.08, 0, pitch);
      put('steel', along, far, mid + 0.8, length, 0.08, 0.08, 0, pitch);
      if (x % 2 === 0) glow(along, f.across, mid + 6.5, 1.6, 0.2, 0.5, WHITE, 6);
    }
  });

  return (
    <>
      <group ref={group} visible={false}>
        {Object.values(parts).map((mesh) => (
          <primitive key={mesh.name} object={mesh} />
        ))}
      </group>
      <StreetRiders />
      <RideMirror />
    </>
  );
}

if (typeof window !== 'undefined') useGLTF.preload(CITY_URL, DRACO_PATH);
