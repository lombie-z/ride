'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import {
  type BufferGeometry,
  Color,
  type InstancedMesh,
  LatheGeometry,
  Matrix4,
  type Mesh,
  MeshPhysicalMaterial,
  type Object3D,
  Quaternion,
  SphereGeometry,
  TorusGeometry,
  Vector2,
  Vector3,
} from 'three';
import { ride, road } from '@/lib/ride';
import { AT } from './bike';

// The black ooze dripping off the gantry: at each strand's tip a drop swells, sags on a lengthening neck, lets go,
// falls, and lands in the pool on the deck with a small crown and a few flung flecks. Slow and heavy, like oil. The
// tips are found in the city model's drip strands at runtime (the model's still being worked on), so the drops follow
// whatever strands it has.

const DECK_Y = -11;
const GRAVITY = 9.8;
const FLECKS = 5;

interface Tip {
  at: Vector3;
  /** The drop's full radius (m). */
  radius: number;
  /** Seconds per drip, and where in it this one starts. */
  period: number;
  phase: number;
  /** Where its drops land (the deck under it), and the fall's length. */
  floor: number;
  /** Each fleck's sideways velocity (x, z) and upward kick. */
  flecks: Vector3[];
}

/**
 * The strands' tips: the lowest point of each separate piece of the drip meshes (the strands and their end beads),
 * merged where a bead hangs off a strand. World space.
 */
export function findTips(scene: Object3D) {
  scene.updateMatrixWorld(true);
  const found: { at: Vector3; width: number }[] = [];
  scene.traverse((o) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh || !/drip/i.test(mesh.name)) return;
    const geometry = mesh.geometry as BufferGeometry;
    const pos = geometry.getAttribute('position');
    const index = geometry.getIndex();
    // Union the vertices of each triangle, welding coincident ones (split normals/uvs), into connected pieces.
    const parent = new Int32Array(pos.count).map((_, i) => i);
    const root = (i: number): number => {
      while (parent[i] !== i) {
        parent[i] = parent[parent[i]];
        i = parent[i];
      }
      return i;
    };
    const join = (a: number, b: number) => {
      const ra = root(a);
      const rb = root(b);
      if (ra !== rb) parent[ra] = rb;
    };
    const welded = new Map<string, number>();
    for (let i = 0; i < pos.count; i++) {
      const key = `${pos.getX(i).toFixed(3)},${pos.getY(i).toFixed(3)},${pos.getZ(i).toFixed(3)}`;
      const other = welded.get(key);
      if (other === undefined) welded.set(key, i);
      else join(i, other);
    }
    const triangles = index ? index.count : pos.count;
    for (let t = 0; t < triangles; t += 3) {
      const a = index ? index.getX(t) : t;
      const b = index ? index.getX(t + 1) : t + 1;
      const c = index ? index.getX(t + 2) : t + 2;
      join(a, b);
      join(b, c);
    }
    const pieces = new Map<number, { low: Vector3; min: Vector2; max: Vector2 }>();
    const p = new Vector3();
    for (let i = 0; i < pos.count; i++) {
      p.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
      const r = root(i);
      let piece = pieces.get(r);
      if (!piece) {
        piece = { low: p.clone(), min: new Vector2(p.x, p.z), max: new Vector2(p.x, p.z) };
        pieces.set(r, piece);
      }
      if (p.y < piece.low.y) piece.low.copy(p);
      piece.min.min(new Vector2(p.x, p.z));
      piece.max.max(new Vector2(p.x, p.z));
    }
    for (const { low, min, max } of pieces.values()) found.push({ at: low, width: Math.min(max.x - min.x, max.y - min.y) });
  });
  // A bead and the strand it ends: keep the lower.
  const tips: { at: Vector3; width: number }[] = [];
  for (const f of found.sort((a, b) => a.at.y - b.at.y)) {
    if (!tips.some((t) => Math.hypot(t.at.x - f.at.x, t.at.z - f.at.z) < 0.12)) tips.push(f);
  }
  return tips;
}

const random = (seed: number) => {
  const x = Math.sin(seed * 127.1) * 43758.5453;
  return x - Math.floor(x);
};

/** A drop's shape: round and heavy below, drawn to a point at the top (y 0 to -1, half a unit across). */
function dropGeometry() {
  const points: Vector2[] = [];
  const steps = 14;
  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    points.push(new Vector2(0.5 * Math.sin(Math.PI * t ** 1.45) ** 0.62, -t));
  }
  return new LatheGeometry(points, 12);
}

const m = new Matrix4();
const q = new Quaternion();
const flat = new Quaternion().setFromAxisAngle(new Vector3(1, 0, 0), Math.PI / 2);
const s = new Vector3();
const v = new Vector3();
const hidden = new Matrix4().makeScale(0, 0, 0);

export function Ooze({ scene, opacity }: { scene: Object3D; opacity: { current: number } }) {
  const drops = useRef<InstancedMesh>(null);
  const crowns = useRef<InstancedMesh>(null);
  const flecks = useRef<InstancedMesh>(null);

  const { tips, material, geometries } = useMemo(() => {
    const tips: Tip[] = findTips(scene).map(({ at, width }, i) => {
      // A drop a little fatter than the bead it grows from.
      const radius = Math.min(0.075, Math.max(0.03, width * 0.6));
      return {
        at,
        radius,
        period: 3.2 + random(i + 1) * 3.8,
        phase: random(i + 7),
        floor: DECK_Y + 0.012,
        flecks: Array.from({ length: FLECKS }, (_, k) => {
          const a = ((k + random(i * 7 + k)) / FLECKS) * Math.PI * 2;
          const speed = 0.25 + random(i * 13 + k) * 0.35;
          return new Vector3(Math.cos(a) * speed, 0.6 + random(i * 17 + k) * 0.6, Math.sin(a) * speed);
        }),
      };
    });
    // Glossy black oil, as the strands (city.tsx's CityOoze).
    const material = new MeshPhysicalMaterial({
      color: new Color(0.004, 0.004, 0.005),
      roughness: 0.12,
      clearcoat: 1,
      clearcoatRoughness: 0.08,
      specularIntensity: 1,
      transparent: true,
    });
    return {
      tips,
      material,
      geometries: { drop: dropGeometry(), crown: new TorusGeometry(1, 0.22, 6, 18), fleck: new SphereGeometry(1, 8, 6) },
    };
  }, [scene]);

  // How far down the road (as ride.drive.s) the last of the drips is: once well past it they're behind the camera for
  // good, and aren't drawn or animated (they're instanced, so nothing culls them).
  const lastTip = useRef<number | null>(null);

  useFrame(({ clock }) => {
    const d = drops.current;
    const c = crowns.current;
    const f = flecks.current;
    if (!d || !c || !f) return;
    if (lastTip.current === null && road.known) {
      lastTip.current = Math.max(...tips.map(({ at }) => (at.x - AT[0]) * road.ahead.x + (at.z - AT[2]) * road.ahead.z));
    }
    const gone = lastTip.current !== null && ride.drive.s > lastTip.current + 25;
    d.visible = c.visible = f.visible = !gone;
    if (gone) return;
    material.opacity = Math.min(1, opacity.current * 1.5);
    const show = opacity.current > 0.01;
    tips.forEach((tip, i) => {
      const r = tip.radius;
      const local = ((clock.elapsedTime / tip.period + tip.phase) % 1) * tip.period;
      // Swell for most of the cycle, then let go: the drop's top stays on the tip while its neck draws out.
      const grow = tip.period * 0.72;
      const fallFrom = tip.at.y - r * 0.2;
      const neck = 2 * r * 1.35;
      const fallTime = Math.sqrt((2 * Math.max(0.01, fallFrom - neck - tip.floor)) / GRAVITY);
      let crownAt = -1;
      if (!show) d.setMatrixAt(i, hidden);
      else if (local < grow) {
        const k = local / grow;
        const size = r * (0.25 + 0.75 * k ** 0.8);
        // Sags slowly, then the neck stretches in the last moments.
        const length = 2 * size * (1 + 0.15 * k + 0.5 * Math.max(0, (k - 0.82) / 0.18) ** 2);
        m.compose(s.set(tip.at.x, fallFrom, tip.at.z), q.identity(), v.set(size * 2, length, size * 2));
        d.setMatrixAt(i, m);
      } else if (local < grow + fallTime) {
        const t = local - grow;
        // Falling: the neck snaps back, the drop rounds (a little long, as falling drops are).
        const top = fallFrom - 0.5 * GRAVITY * t * t - 0.12 * r * Math.min(1, t * 8);
        const length = 2 * r * (1.65 - 0.35 * Math.min(1, t * 5));
        m.compose(s.set(tip.at.x, top, tip.at.z), q.identity(), v.set(r * 1.8, length, r * 1.8));
        d.setMatrixAt(i, m);
      } else {
        d.setMatrixAt(i, hidden);
        crownAt = local - grow - fallTime;
      }
      // The landing: a crown spreading and sinking back into the pool, and flecks flung out.
      if (crownAt >= 0 && crownAt < 0.7) {
        const k = crownAt / 0.7;
        const spread = r * (0.8 + 2.2 * Math.sqrt(k));
        const height = r * 0.9 * (1 - k) ** 1.5;
        m.compose(s.set(tip.at.x, tip.floor, tip.at.z), flat, v.set(spread, spread, Math.max(0.0001, height)));
        c.setMatrixAt(i, m);
      } else c.setMatrixAt(i, hidden);
      for (let k = 0; k < FLECKS; k++) {
        const t = crownAt;
        const kick = tip.flecks[k];
        const y = tip.floor + kick.y * t - 0.5 * GRAVITY * t * t;
        if (crownAt >= 0 && y > tip.floor - 0.005) {
          const size = r * 0.18 * (1 - random(i * 31 + k) * 0.5);
          m.compose(s.set(tip.at.x + kick.x * t, y, tip.at.z + kick.z * t), q.identity(), v.set(size, size * 1.3, size));
          f.setMatrixAt(i * FLECKS + k, m);
        } else f.setMatrixAt(i * FLECKS + k, hidden);
      }
    });
    d.instanceMatrix.needsUpdate = true;
    c.instanceMatrix.needsUpdate = true;
    f.instanceMatrix.needsUpdate = true;
  });

  if (!tips.length) return null;
  return (
    <>
      <instancedMesh ref={drops} name="OozeDrops" args={[geometries.drop, material, tips.length]} frustumCulled={false} />
      <instancedMesh ref={crowns} name="OozeCrowns" args={[geometries.crown, material, tips.length]} frustumCulled={false} />
      <instancedMesh ref={flecks} name="OozeFlecks" args={[geometries.fleck, material, tips.length * FLECKS]} frustumCulled={false} />
    </>
  );
}
