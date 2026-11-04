'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { CanvasTexture, Color, Mesh, MeshBasicMaterial, PlaneGeometry } from 'three';
import { course } from '@/lib/course';

// Where one city's way out meets the next one's road: the next's surface reaching back over the old in patches, thickening
// toward the join, so it's a change rather than a line across the road. Drawn in the next city's frame, whose +x runs on
// from the way out's last heading (lib/course.ts placeAfter).

/** How far back over the old road it reaches (m), how far on over its own, its width, and each zone's road colour. */
const BACK = 190;
const ON = 56;
const WIDTH = 11.5;
const SURFACE: Record<number, string> = { 2: '#46303a', 3: '#d9a062' };

/** Alpha: none far back, thick at the join, thinning out again past it onto the new road, all in blotches. */
function reach() {
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
  for (let y = 0; y < h; y++) {
    // (Row 0 is the plane's far end, v 1: the join's side.)
    const along = 1 - y / (h - 1);
    for (let x = 0; x < w; x++) {
      const blotch = 0.6 * noise(x * 0.11, y * 0.05) + 0.3 * noise(x * 0.31, y * 0.14) + 0.1 * noise(x * 0.9, y * 0.4);
      const join = BACK / (BACK + ON);
      const edge = along < join ? (along - 0.1) / (join - 0.1) : 1 - (along - join) / (1 - join);
      const a = 0.92 * Math.min(1, Math.max(0, (edge * 1.3 - blotch + 0.12) / 0.09));
      const i = (x + y * w) * 4;
      image.data[i] = image.data[i + 1] = image.data[i + 2] = a * 255;
      image.data[i + 3] = 255;
    }
  }
  g.putImageData(image, 0, 0);
  return new CanvasTexture(canvas);
}

export function RoadJoin({ k }: { k: number }) {
  const mesh = useMemo(() => {
    const geometry = new PlaneGeometry(BACK + ON, WIDTH);
    // (Its u along the road: turned so u runs along +x, and laid flat; just over the deck and the mirror.)
    geometry.rotateX(-Math.PI / 2);
    geometry.translate((ON - BACK) / 2, 0.06, 0);
    const uv = geometry.attributes.uv;
    for (let i = 0; i < uv.count; i++) uv.setXY(i, uv.getY(i), uv.getX(i));
    const material = new MeshBasicMaterial({ color: new Color(SURFACE[k] ?? '#3a3030'), alphaMap: reach(), transparent: true, depthWrite: false });
    const m = new Mesh(geometry, material);
    m.name = 'RoadJoin';
    m.renderOrder = 2;
    return m;
  }, [k]);
  useEffect(
    () => () => {
      mesh.geometry.dispose();
      const material = mesh.material as MeshBasicMaterial;
      material.alphaMap?.dispose();
      material.dispose();
    },
    [mesh]
  );
  useFrame(() => {
    mesh.visible = course.legs[k].placed;
  });
  return <primitive object={mesh} />;
}
