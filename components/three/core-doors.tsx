'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import {
  BoxGeometry,
  CanvasTexture,
  Color,
  DoubleSide,
  Group,
  Mesh,
  MeshBasicMaterial,
  NearestFilter,
  PlaneGeometry,
  RingGeometry,
  SRGBColorSpace,
} from 'three';
import { course, groundAt, legToWorld, pathAt } from '@/lib/course';
import { DOORS, doorOpen, doorState, doors } from '@/lib/doors';
import { memory } from '@/lib/memory';
import { ride } from '@/lib/ride';

// The core's doors on its road (lib/doors.ts): two leaves for those the city doesn't have of its own, and on every one the segments its
// wins light. Painted flat, like the city's baked surfaces: this is seen at a seventh of the resolution.

const LEAF_DEPTH = 0.5;
const DARK = 0.32;
const GLOW = 2.4;

type Built = { root: Group; left: Group; right: Group; segments: Mesh<PlaneGeometry | RingGeometry, MeshBasicMaterial>[]; width: number };

/** A leaf's face: hard bands of plate, seams and a hazard strip, its rust. */
function leafTexture(plate: string, seam: string, hazard: boolean) {
  const c = document.createElement('canvas');
  c.width = 64;
  c.height = 64;
  const g = c.getContext('2d') as CanvasRenderingContext2D;
  g.fillStyle = plate;
  g.fillRect(0, 0, 64, 64);
  g.fillStyle = seam;
  for (let y = 8; y < 64; y += 14) g.fillRect(0, y, 64, 1);
  for (let x = 6; x < 64; x += 19) g.fillRect(x, 0, 1, 64);
  if (hazard) {
    for (let x = -16; x < 64; x += 8) {
      g.fillStyle = '#d8b400';
      for (let i = 0; i < 6; i++) g.fillRect(x + i, 52 + i, 4, 1);
    }
  }
  g.fillStyle = 'rgba(70, 40, 20, 0.5)';
  for (let i = 0; i < 9; i++) g.fillRect((i * 29) % 64, (i * 17) % 40, 1, 6 + ((i * 5) % 14));
  const t = new CanvasTexture(c);
  t.magFilter = NearestFilter;
  t.minFilter = NearestFilter;
  t.colorSpace = SRGBColorSpace;
  return t;
}

const FACES = [
  { plate: '#596871', seam: '#2c343a', hazard: true },
  null,
  { plate: '#4b3019', seam: '#22140a', hazard: false },
  { plate: '#0b1a12', seam: '#1a4a2e', hazard: false },
];

function build(i: number): Built {
  const d = DOORS[i];
  const root = new Group();
  const left = new Group();
  const right = new Group();
  root.add(left, right);
  const face = FACES[i];
  const width = d.width || 14.2;
  const height = d.height || 8.2;
  if (d.width && face) {
    const map = leafTexture(face.plate, face.seam, face.hazard);
    const material = new MeshBasicMaterial({ map });
    for (const side of [left, right]) {
      const leaf = new Mesh(new BoxGeometry(LEAF_DEPTH, height, width / 2), material);
      leaf.position.set(0, height / 2, side === left ? -width / 4 : width / 4);
      side.add(leaf);
    }
  }
  const segments: Built['segments'] = [];
  const front = d.width ? -LEAF_DEPTH / 2 - 0.04 : -0.62;
  const count = d.rounds.length;
  const add = (m: Mesh<PlaneGeometry | RingGeometry, MeshBasicMaterial>, onLeft: boolean, y: number, z: number) => {
    m.position.set(front, y, z);
    m.rotation.y = -Math.PI / 2;
    (onLeft ? left : right).add(m);
    segments.push(m);
  };
  const material = () => new MeshBasicMaterial({ color: d.look.dark, toneMapped: false, side: DoubleSide });
  // (The bulkhead's its own lamps and wheel, on the tunnel's door: components/three/core-sections.tsx.)
  if (d.look.lock === 'wheel') {
  } else if (d.look.lock === 'rings') {
    // Arcs round the door's middle, in order round the clock from the top; each on whichever leaf it mostly lies on.
    const inner = height * 0.27;
    const outer = height * 0.4;
    const gap = 0.05;
    for (let k = 0; k < count; k++) {
      const a0 = Math.PI / 2 - ((k + 1) / count) * Math.PI * 2 + gap;
      const sweep = (Math.PI * 2) / count - gap * 2;
      const mid = a0 + sweep / 2;
      // (Local x, looking at it from the rider's side, runs to their right: the door's +z.)
      add(new Mesh(new RingGeometry(inner, outer, 28, 1, a0, sweep), material()), Math.cos(mid) < 0, height / 2, 0);
    }
  } else {
    // A quadrant of each leaf, in order round the clock from the top left.
    const w = width * 0.34;
    const h = height * (d.width ? 0.34 : 0.28);
    const spots = [
      [-1, 1],
      [1, 1],
      [1, -1],
      [-1, -1],
    ];
    for (let k = 0; k < count; k++) {
      const [sx, sy] = spots[k % 4];
      add(new Mesh(new PlaneGeometry(w, h), material()), sx < 0, height * (0.5 + sy * 0.23), (sx * width) / 4);
    }
  }
  root.visible = false;
  return { root, left, right, segments, width };
}

const red = new Color('#ff2010');
const on = new Color();
const off = new Color();

export function CoreDoors() {
  const holder = useRef<Group>(null);
  const built = useMemo(() => (typeof document === 'undefined' ? [] : DOORS.map((_, i) => build(i))), []);
  useEffect(() => {
    const g = holder.current;
    if (!g) return;
    for (const b of built) g.add(b.root);
    return () => {
      for (const b of built) g.remove(b.root);
    };
  }, [built]);

  useFrame(() => {
    const leg = course.legs[4];
    built.forEach((b, i) => {
      const d = DOORS[i];
      if (!leg.placed || !leg.in || d.at === null) {
        b.root.visible = false;
        return;
      }
      const open = doorOpen(i);
      // (Only near enough to be seen: the sections it's in may not be drawn.)
      b.root.visible = open < 1 && Math.abs(ride.drive.s - leg.at - d.at) < 900;
      if (!b.root.visible) return;
      const at = pathAt(leg.in, d.at);
      legToWorld(leg, at.x, at.y, b.root.position);
      b.root.position.y += groundAt(leg.at + d.at);
      b.root.rotation.y = leg.yaw + at.heading;
      b.left.position.z = -(b.width / 2) * open * 0.98;
      b.right.position.z = (b.width / 2) * open * 0.98;
      const lit = doorState[i].lit;
      const alarm = doors.current === i ? memory.flash : 0;
      on.set(d.look.lit).multiplyScalar(GLOW);
      off
        .set(d.look.dark)
        .multiplyScalar(DARK * 2)
        .lerp(red, alarm);
      b.segments.forEach((s, k) => {
        s.material.color.copy(k < lit ? on : off);
      });
    });
  });

  return <group ref={holder} />;
}
