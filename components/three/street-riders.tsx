'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { AdditiveBlending, BufferAttribute, BufferGeometry, DynamicDrawUsage, Mesh, type PerspectiveCamera, ShaderMaterial, Vector3 } from 'three';
import { isLightDevice, smoothstep } from '@/lib/journey';
import { CRUISE, ride, road } from '@/lib/ride';
import { type Branch, DECK_Y, FLYOVERS, flyoverY, HALF, hash, type Over, TILE, tileAt } from '@/lib/street';
import { AT } from './bike';

// Other riders down the green city's street, seen only as light: long blurred streaks, green going white at the head,
// each with one hard red point for a tail lamp. They come up from behind, hang beside the bike a moment, pass, peel off
// down the side streets and cross ahead on the overpasses. One mesh, its ribbons rewritten every frame, billboarded to
// the camera; additive and past white, so the bloom takes them and the wet road mirrors them. They're spawned as the
// bike crosses each tile, from its index (lib/street.ts), so it's the same ride each time.

const STARTS_AFTER = 8; // s of riding before the first of them
const SEGMENTS = 7;
const VERTS = (SEGMENTS + 1) * 2 + 4;
const INDICES = SEGMENTS * 6 + 6;

// What each is doing: down the road past the bike; alongside for a moment first; off down a side street; across an
// overpass; along a flyover; straight off down a side street as the bike passes its mouth.
type Kind = 'pass' | 'hang' | 'peel' | 'cross' | 'fly' | 'street';
type Rider = {
  live: boolean;
  kind: Kind;
  /** Metres along its path: for those on the road, the same as along the street. */
  u: number;
  /** Faster than the bike (m/s), or for those off the road its own speed. */
  v: number;
  lane: number;
  weave: number;
  phase: number;
  length: number;
  width: number;
  hot: number;
  white: number;
  age: number;
  /** Alongside: how far ahead of the bike it holds, and for how long. */
  hold: number;
  holdFor: number;
  /** Off down a side street: where it starts to turn, its radius, and the street. */
  turnAt: number;
  radius: number;
  branch: Branch | null;
  over: Over | null;
  way: number;
  fly: number;
  /** How high its light is over the road. */
  rise: number;
};

const blank = (): Rider => ({
  live: false,
  kind: 'pass',
  u: 0,
  v: 0,
  lane: 0,
  weave: 0,
  phase: 0,
  length: 0,
  width: 0,
  hot: 0,
  white: 0,
  age: 0,
  hold: 0,
  holdFor: 0,
  turnAt: 0,
  radius: 0,
  branch: null,
  over: null,
  way: 1,
  fly: 0,
  rise: 0.85,
});

// The point on a rider's path, in the street's frame (along, across, height).
const here = { a: 0, c: 0, y: 0 };
function pathAt(r: Rider, u: number) {
  here.y = DECK_Y + r.rise;
  switch (r.kind) {
    case 'pass':
    case 'hang':
      here.a = u;
      here.c = r.lane + r.weave * Math.sin(u / 46 + r.phase);
      return;
    case 'peel': {
      const b = r.branch as Branch;
      const d = u - r.turnAt;
      if (d <= 0) {
        here.a = u;
        here.c = r.lane;
        return;
      }
      const arc = r.radius * b.angle;
      if (d < arc) {
        const f = d / r.radius;
        here.a = r.turnAt + r.radius * Math.sin(f);
        here.c = r.lane + b.side * r.radius * (1 - Math.cos(f));
        return;
      }
      const on = d - arc;
      here.a = r.turnAt + r.radius * b.sin + on * b.cos;
      here.c = r.lane + b.side * (r.radius * (1 - b.cos) + on * b.sin);
      return;
    }
    case 'street': {
      const b = r.branch as Branch;
      here.a = b.at + u * b.cos;
      here.c = b.side * (HALF + u * b.sin);
      return;
    }
    case 'cross': {
      const o = r.over as Over;
      here.a = o.at + r.way * u * Math.cos(o.turn) - 2 * Math.sin(o.turn);
      here.c = -r.way * u * Math.sin(o.turn) - 2 * Math.cos(o.turn);
      here.y = o.y + 0.95;
      return;
    }
    case 'fly': {
      const f = FLYOVERS[r.fly];
      here.a = u;
      here.c = f.across + r.lane;
      here.y = flyoverY(f, u / TILE) + 0.85;
      return;
    }
  }
}

const p = new Vector3();
const q = new Vector3();
const tangent = new Vector3();
const toCamera = new Vector3();
const across = new Vector3();
const eyeRight = new Vector3();
const eyeUp = new Vector3();

export function StreetRiders() {
  const { mesh, riders, positions, tints } = useMemo(() => {
    const count = isLightDevice() ? 11 : 22;
    const riders = Array.from({ length: count }, blank);
    const geometry = new BufferGeometry();
    const positions = new BufferAttribute(new Float32Array(count * VERTS * 3), 3);
    // (Its colour and, in the last, where it is across the ribbon: -1 to 1, or 2 for a hard edge.)
    const tints = new BufferAttribute(new Float32Array(count * VERTS * 4), 4);
    positions.setUsage(DynamicDrawUsage);
    tints.setUsage(DynamicDrawUsage);
    geometry.setAttribute('position', positions);
    geometry.setAttribute('aTint', tints);
    const index = new Uint16Array(count * INDICES);
    for (let i = 0, n = 0; i < count; i++) {
      const base = i * VERTS;
      for (let s = 0; s < SEGMENTS; s++) {
        const a = base + s * 2;
        index[n++] = a;
        index[n++] = a + 1;
        index[n++] = a + 2;
        index[n++] = a + 1;
        index[n++] = a + 3;
        index[n++] = a + 2;
      }
      const t = base + (SEGMENTS + 1) * 2;
      index[n++] = t;
      index[n++] = t + 1;
      index[n++] = t + 2;
      index[n++] = t + 1;
      index[n++] = t + 3;
      index[n++] = t + 2;
    }
    geometry.setIndex(new BufferAttribute(index, 1));
    geometry.setDrawRange(0, 0);
    const material = new ShaderMaterial({
      transparent: true,
      blending: AdditiveBlending,
      depthWrite: false,
      toneMapped: false,
      vertexShader: /* glsl */ `
        attribute vec4 aTint;
        varying vec4 vTint;
        void main() {
          vTint = aTint;
          gl_Position = projectionMatrix * viewMatrix * vec4(position, 1.0);
        }`,
      fragmentShader: /* glsl */ `
        varying vec4 vTint;
        void main() {
          // Soft across the ribbon: a hot thin core in a wide glow. The tail lamp's flat, hard edged.
          float v = vTint.a;
          float light = v > 1.5 ? 1.0 : exp(-v * v * 26.0) + 0.3 * exp(-v * v * 3.2) * (1.0 - v * v);
          gl_FragColor = vec4(vTint.rgb * light, 1.0);
          #include <colorspace_fragment>
        }`,
    });
    const mesh = new Mesh(geometry, material);
    mesh.name = 'StreetRiders';
    mesh.frustumCulled = false;
    mesh.renderOrder = 5;
    mesh.visible = false;
    return { mesh, riders, positions, tints };
  }, []);
  useEffect(
    () => () => {
      mesh.geometry.dispose();
      (mesh.material as ShaderMaterial).dispose();
    },
    [mesh]
  );

  const state = useMemo(() => ({ lastS: 0, lastTile: Number.NaN, side: new Vector3(), line: 0 }), []);

  const take = () => {
    for (const r of riders) {
      if (r.live) continue;
      r.live = true;
      r.age = 0;
      r.weave = 0;
      r.branch = null;
      r.over = null;
      r.hold = 0;
      return r;
    }
    return null;
  };
  const dress = (r: Rider, seed: number) => {
    // (Far longer than any bike: a long exposure's trail, which is all that's seen of them.)
    r.length = 30 + hash(seed, 1) * 38;
    r.width = 0.7 + hash(seed, 2) * 0.45;
    r.hot = 2.6 + hash(seed, 3) * 2.6;
    r.rise = 0.45 + hash(seed, 19) * 1.05;
    r.white = hash(seed, 4) * 0.7;
    r.phase = hash(seed, 5) * 6.28;
  };
  // A lane to the right of the bike's line (it rides near the left barrier: there's no room that side).
  const laneAt = (seed: number) => state.line + 2.3 + hash(seed, 6) * Math.max(0, HALF - 1 - state.line - 2.3);

  const pass = (k: number, n: number, at: number) => {
    const r = take();
    if (!r) return;
    const seed = k + n * 0.41;
    dress(r, seed);
    r.kind = 'pass';
    r.lane = laneAt(seed);
    r.weave = hash(seed, 7) * 0.9;
    r.u = at - 34 - hash(seed, 8) * 30 - n * 9;
    r.v = 10 + hash(seed, 9) * 16;
  };
  const hang = (k: number, at: number) => {
    const r = take();
    if (!r) return;
    dress(r, k + 0.5);
    r.kind = 'hang';
    r.lane = laneAt(k + 0.5);
    r.u = at - 30;
    r.v = 26;
    r.hold = 7 + hash(k, 10) * 7;
    r.holdFor = 1.5 + hash(k, 11) * 1.4;
    r.width *= 0.8;
  };
  const peel = (b: Branch) => {
    const r = take();
    if (!r) return;
    dress(r, b.k + 0.7);
    r.kind = 'peel';
    r.branch = b;
    r.lane = laneAt(b.k + 0.7);
    r.radius = 34 + hash(b.k, 12) * 16;
    // (So the end of its turn lands on the street's centre line.)
    r.turnAt = b.at + (b.side * r.lane + r.radius * (1 - b.cos) - HALF) / Math.tan(b.angle) - r.radius * b.sin;
    r.v = 20;
    r.u = state.lastS - road.end - 36;
  };
  const cross = (o: Over, startAt: number) => {
    const r = take();
    if (!r) return;
    dress(r, o.k + 0.3);
    r.kind = 'cross';
    r.over = o;
    r.way = hash(o.k, 13) > 0.5 ? 1 : -1;
    r.v = 58;
    r.u = -startAt;
    r.length *= 1.2;
  };
  const fly = (index: number, k: number, at: number) => {
    const r = take();
    if (!r) return;
    dress(r, k + index + 0.9);
    r.kind = 'fly';
    r.fly = index;
    r.lane = (hash(k, 14) - 0.5) * 3;
    r.u = at - 40;
    r.v = 12 + hash(k, 15) * 20;
    r.length *= 1.3;
  };
  const leaveBy = (b: Branch) => {
    const r = take();
    if (!r) return;
    dress(r, b.k + 0.2);
    r.kind = 'street';
    r.branch = b;
    r.v = 44;
    r.u = 6;
  };

  /** Crossing onto tile k: who comes along now. */
  const onTile = (k: number, at: number) => {
    const tile = tileAt(k);
    // Those going off down a side street, while it's still a fair way ahead (they've to catch and pass the bike first).
    for (const b of tileAt(k + 10).branches) if (hash(b.k, 16) > 0.1) peel(b);
    // Someone on each overpass as the bike comes up to it, crossing its road a moment before it's under.
    const over = tileAt(k + 5).over;
    if (over && hash(over.k, 17) > 0.08) {
      const ahead = over.at - at;
      cross(over, (58 * Math.max(0, ahead - 34)) / Math.max(ride.drive.speed, 20));
    }
    // And away down the side street it's about to pass.
    for (const b of tileAt(k + 2).branches) if (hash(b.k, 18) > 0.35) leaveBy(b);
    const r = (n: number) => hash(k, n + 50);
    if (tile.phase === 'open') {
      if (k === 2 || r(1) > 0.84) hang(k, at);
      else if (k === 6 || r(2) > 0.8) pass(k, 0, at);
      for (let i = 0; i < FLYOVERS.length; i++) {
        const f = FLYOVERS[i];
        if (k >= f.from + 2 && k < f.to - 6 && r(3 + i) > 0.68) fly(i, k, at);
      }
    } else if (tile.phase === 'streets') {
      if (r(1) > 0.82) pass(k, 0, at);
      else if (r(2) > 0.86) hang(k, at);
    } else if (tile.phase === 'through') {
      // In the halls, at a steady rate: they're what the light on the wet floor is about.
      if (tile.hall?.i === 0) hang(k, at);
      else if (r(1) > 0.42) pass(k, 0, at);
    } else if (r(1) > 0.4) {
      // The canyon: the pack comes through, more together as it goes on.
      const pack = 1 + Math.floor(r(2) * 2.4);
      for (let n = 0; n < pack; n++) pass(k, n, at);
    }
  };

  useFrame(({ camera, gl, size }, delta) => {
    const dt = Math.min(delta, 0.1);
    const drive = ride.drive;
    const tr = ride.transition;
    const s = drive.s;
    // On the way back to the landing, or put back after the wash: they're gone.
    if (s < state.lastS - 0.5) for (const r of riders) r.live = false;
    const moved = s !== state.lastS;
    state.lastS = s;
    // They go as the chrome city's light comes in.
    const fade = Math.min(1, ride.mount * 2) * (1 - smoothstep(0.12, 0.42, tr.t));
    mesh.visible = road.known && ride.zone === 1 && fade > 0.001;
    if (!mesh.visible) {
      for (const r of riders) r.live = false;
      mesh.geometry.setDrawRange(0, 0);
      state.lastTile = Number.NaN;
      return;
    }
    const side = state.side.set(-road.ahead.z, 0, road.ahead.x);
    state.line = side.x * (AT[0] - road.endCentre.x) + side.z * (AT[2] - road.endCentre.z);
    const at = s - road.end;
    const tile = Math.floor(at / TILE);
    if (moved && tile !== state.lastTile) {
      const jump = Math.abs(tile - state.lastTile) > 2;
      state.lastTile = tile;
      // (Not once the road ahead's been handed to the chrome city, not on a dev jump down the road.)
      if (ride.mounted && drive.time > STARTS_AFTER && !tr.placed && !jump) onTile(tile, at);
    }

    const cam = camera as PerspectiveCamera;
    // A thin streak far off would fall between the pixels: never narrower than a couple of the buffer's.
    const pixel = (2 * Math.tan((cam.fov * Math.PI) / 360)) / (size.height * gl.getPixelRatio());
    eyeRight.setFromMatrixColumn(cam.matrixWorld, 0);
    eyeUp.setFromMatrixColumn(cam.matrixWorld, 1);
    const pos = positions.array as Float32Array;
    const tint = tints.array as Float32Array;
    let live = 0;
    for (const r of riders) {
      if (!r.live) continue;
      r.age += dt;
      if (r.kind === 'hang') {
        const rel = r.u - at;
        const leaving = r.age > r.holdFor + 1.6 || drive.speed < 18;
        const want = leaving ? 24 : Math.max(-6, Math.min(26, (r.hold - rel) * 1.6));
        r.u += (drive.speed + want) * dt;
      } else if (r.kind === 'cross' || r.kind === 'street') r.u += r.v * dt;
      else r.u += (Math.max(CRUISE, drive.speed) + r.v) * dt;
      // Done: far enough gone, or (in a stop) left behind.
      let done = false;
      if (r.kind === 'cross') done = r.u > 300;
      else if (r.kind === 'street') done = r.u > (r.branch as Branch).length;
      else if (r.kind === 'peel') done = r.u - r.turnAt > (r.branch as Branch).length;
      else if (r.kind === 'fly') done = r.u / TILE > FLYOVERS[r.fly].to - 1;
      else done = r.u - at > 500;
      if (done) {
        r.live = false;
        continue;
      }
      // The ribbon, head to tail.
      pathAt(r, r.u);
      toWorld(p, here.a, here.c, here.y, side);
      const distance = p.distanceTo(cam.position);
      const seen = fade * (1 - smoothstep(80, 540, distance));
      const base = live * VERTS;
      for (let i = 0; i <= SEGMENTS; i++) {
        const t = i / SEGMENTS;
        pathAt(r, r.u - t * r.length);
        toWorld(p, here.a, here.c, here.y, side);
        pathAt(r, r.u - t * r.length - 1);
        toWorld(q, here.a, here.c, here.y, side);
        tangent.copy(p).sub(q);
        toCamera.copy(cam.position).sub(p);
        const d = toCamera.length();
        across.crossVectors(tangent, toCamera).normalize();
        // Comes up fast to the head, dies away slowly down the tail, narrowing.
        const body = Math.min(1, t / 0.06) * (1 - t) ** 1.2;
        const width = Math.max(r.width * (0.35 + 0.65 * (1 - t)), d * pixel * 2.4) * 0.5;
        // (Easing off right up by the camera, where a metre of it fills the screen.)
        const heat = r.hot * body * seen * (0.3 + 0.7 * smoothstep(1, 22, d));
        // White at the head, green down the tail.
        const w = r.white + (1 - r.white) * Math.max(0, 1 - t * 4);
        const cr = 0.3 + 0.62 * w;
        const cb = 0.42 + 0.48 * w;
        const v = base + i * 2;
        pos[v * 3] = p.x + across.x * width;
        pos[v * 3 + 1] = p.y + across.y * width;
        pos[v * 3 + 2] = p.z + across.z * width;
        pos[v * 3 + 3] = p.x - across.x * width;
        pos[v * 3 + 4] = p.y - across.y * width;
        pos[v * 3 + 5] = p.z - across.z * width;
        tint[v * 4] = tint[v * 4 + 4] = cr * heat;
        tint[v * 4 + 1] = tint[v * 4 + 5] = heat;
        tint[v * 4 + 2] = tint[v * 4 + 6] = cb * heat;
        tint[v * 4 + 3] = 1;
        tint[v * 4 + 7] = -1;
      }
      // The tail lamp: a hard red point, a little back from the head.
      pathAt(r, r.u - 3);
      toWorld(p, here.a, here.c, here.y - 0.15, side);
      const size2 = Math.max(0.17, p.distanceTo(cam.position) * pixel * 1.1);
      const t0 = base + (SEGMENTS + 1) * 2;
      for (let c = 0; c < 4; c++) {
        const ux = c & 1 ? size2 : -size2;
        const uy = c & 2 ? size2 : -size2;
        const v = t0 + c;
        pos[v * 3] = p.x + eyeRight.x * ux + eyeUp.x * uy;
        pos[v * 3 + 1] = p.y + eyeRight.y * ux + eyeUp.y * uy;
        pos[v * 3 + 2] = p.z + eyeRight.z * ux + eyeUp.z * uy;
        tint[v * 4] = 7 * seen;
        tint[v * 4 + 1] = 0.12 * seen;
        tint[v * 4 + 2] = 0.08 * seen;
        tint[v * 4 + 3] = 2;
      }
      live++;
    }
    mesh.geometry.setDrawRange(0, live * INDICES);
    positions.needsUpdate = true;
    tints.needsUpdate = true;
  });

  return <primitive object={mesh} />;
}

function toWorld(out: Vector3, a: number, c: number, y: number, side: Vector3) {
  out.copy(road.endCentre).addScaledVector(road.ahead, a).addScaledVector(side, c).setY(y);
}
