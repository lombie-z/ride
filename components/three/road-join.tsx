'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { CanvasTexture, Color, Mesh, MeshBasicMaterial, PlaneGeometry } from 'three';
import { course } from '@/lib/course';

// Where one city's way out meets the next one's road: the next's surface reaching back over the old in patches, thickening
// toward the join, so it's a change rather than a line across the road. Drawn in the next city's frame, whose +x runs on
// from the way out's last heading (lib/course.ts placeAfter).

/** Each join's patches: its colour, how far back over the old road it starts (m), where it's thickest, how far on it runs. */
type Patch = { colour: string; from: number; peak: number; to: number };
const WIDTH = 11.5;
const PATCHES: Record<number, Patch[]> = {
  2: [{ colour: '#46303a', from: -300, peak: -60, to: 56 }],
  3: [
    // (The hive's stone gives way to its asphalt some way out: broken up too, not a line across the road.)
    { colour: '#2c2626', from: -470, peak: -285, to: -210 },
    { colour: '#d9a062', from: -260, peak: -30, to: 60 },
  ],
};

/** Alpha: none at its ends, thick at its peak, all in blotches. (u along the road, from its start to its end.) */
function reach(p: Patch) {
  const w = 64;
  const h = 256;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const g = canvas.getContext('2d') as CanvasRenderingContext2D;
  const image = g.createImageData(w, h);
  const noise = (x: number, y: number) => {
    const n = (a: number, b: number) => {
      const s = Math.sin(a * 127.1 + b * 311.7) * 43758.5453;
      return s - Math.floor(s);
    };
    const ix = Math.floor(x);
    const iy = Math.floor(y);
    const fx = x - ix;
    const fy = y - iy;
    const ux = fx * fx * (3 - 2 * fx);
    const uy = fy * fy * (3 - 2 * fy);
    return (n(ix, iy) * (1 - ux) + n(ix + 1, iy) * ux) * (1 - uy) + (n(ix, iy + 1) * (1 - ux) + n(ix + 1, iy + 1) * ux) * uy;
  };
  const peak = (p.peak - p.from) / (p.to - p.from);
  for (let y = 0; y < h; y++) {
    // (Row 0 is the plane's far end, v 1.)
    const along = 1 - y / (h - 1);
    for (let x = 0; x < w; x++) {
      const blotch = 0.6 * noise(x * 0.11, y * 0.05) + 0.3 * noise(x * 0.31, y * 0.14) + 0.1 * noise(x * 0.9, y * 0.4);
      const edge = along < peak ? along / peak : 1 - (along - peak) / (1 - peak);
      const a = 0.94 * Math.min(1, Math.max(0, (edge * 1.3 - blotch + 0.12) / 0.09));
      const i = (x + y * w) * 4;
      image.data[i] = image.data[i + 1] = image.data[i + 2] = a * 255;
      image.data[i + 3] = 255;
    }
  }
  g.putImageData(image, 0, 0);
  return new CanvasTexture(canvas);
}

export function RoadJoin({ k }: { k: number }) {
  const meshes = useMemo(
    () =>
      (PATCHES[k] ?? []).map((p, i) => {
        const geometry = new PlaneGeometry(p.to - p.from, WIDTH);
        // (Its v along the road: laid flat, just over the deck and the mirror, u and v swapped.)
        geometry.rotateX(-Math.PI / 2);
        geometry.translate((p.from + p.to) / 2, 0.06 + i * 0.004, 0);
        const uv = geometry.attributes.uv;
        for (let n = 0; n < uv.count; n++) uv.setXY(n, uv.getY(n), uv.getX(n));
        const material = new MeshBasicMaterial({ color: new Color(p.colour), alphaMap: reach(p), transparent: true, depthWrite: false });
        const m = new Mesh(geometry, material);
        m.name = 'RoadJoin';
        m.renderOrder = 2 + i;
        return m;
      }),
    [k]
  );
  useEffect(
    () => () => {
      for (const mesh of meshes) {
        mesh.geometry.dispose();
        const material = mesh.material as MeshBasicMaterial;
        material.alphaMap?.dispose();
        material.dispose();
      }
    },
    [meshes]
  );
  useFrame(() => {
    for (const mesh of meshes) mesh.visible = course.legs[k].placed;
  });
  return (
    <>
      {meshes.map((m) => (
        <primitive key={m.uuid} object={m} />
      ))}
    </>
  );
}
