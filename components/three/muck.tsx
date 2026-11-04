'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { CanvasTexture, Color, IcosahedronGeometry, InstancedMesh, Matrix4, MeshBasicMaterial, Object3D, PlaneGeometry } from 'three';
import { course, pathAt } from '@/lib/course';
import { NO_MIRROR_LAYER } from '@/lib/journey';
import { eyePuddles, muckSlicks, zoneRoad } from '@/lib/ride';
import { eyePuddleMaterial, voidGloop } from './void-gloop';

// The slicks of black ooze on a city's road (lib/ride.ts muckSlicks), raised gooey lumps, windows onto the void.
// Drawn in the city's own frame (a child of its group): three's axes, x along the road in, z to its right.

/** A lumpy, flattened blob: an icosphere pushed about by a little noise, its underside flat on the road. */
function blob(detail = 3) {
  const g = new IcosahedronGeometry(1, detail);
  const p = g.attributes.position;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i);
    const y = p.getY(i);
    const z = p.getZ(i);
    const k = 1 + 0.18 * Math.sin(x * 4.1 + z * 2.3) * Math.cos(z * 3.7 - x * 1.9);
    p.setXYZ(i, x * k, Math.max(0, y) * k, z * k);
  }
  g.computeVertexNormals();
  return g;
}

/** A soft dark stain round each slick on the road: the ooze seeping out, so its edges blend into the ground. */
function stain() {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d') as CanvasRenderingContext2D;
  const g = ctx.createRadialGradient(size / 2, size / 2, size * 0.18, size / 2, size / 2, size / 2);
  g.addColorStop(0, 'rgba(255,255,255,0.95)');
  g.addColorStop(0.55, 'rgba(255,255,255,0.45)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const material = new MeshBasicMaterial({ color: new Color(0, 0, 0), alphaMap: new CanvasTexture(canvas), transparent: true, depthWrite: false });
  return material;
}

export function Muck({ k }: { k: number }) {
  const mesh = useMemo(() => {
    const slicks = muckSlicks(k);
    // (A window onto somewhere else, reflecting nothing (components/three/void-gloop.ts); and not drawn into the road's
    // mirror, so nothing reflects it as a floating shape either.)
    const m = new InstancedMesh(blob(), voidGloop(), slicks.length);
    m.layers.set(NO_MIRROR_LAYER);
    m.name = 'Muck';
    m.frustumCulled = false;
    const o = new Object3D();
    slicks.forEach((s, i) => {
      const at = pathAt(zoneRoad(k), s.u);
      // Across the road: to the left of its heading (Blender's frame), so in three's, (-sin, -cos) on x, z.
      o.position.set(at.x - Math.sin(at.heading) * s.across, 0, -(at.y + Math.cos(at.heading) * s.across));
      o.rotation.set(0, at.heading + s.turn, 0);
      o.scale.set(s.along, s.height, s.wide);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    return m;
  }, [k]);
  // The stains: flat discs a size larger than each slick, just above the road.
  const stains = useMemo(() => {
    const slicks = muckSlicks(k);
    const disc = new PlaneGeometry(1, 1).rotateX(-Math.PI / 2);
    const m = new InstancedMesh(disc, stain(), slicks.length);
    m.name = 'MuckStains';
    m.frustumCulled = false;
    m.renderOrder = 1;
    const o = new Object3D();
    const at = new Matrix4();
    slicks.forEach((s, i) => {
      mesh.getMatrixAt(i, at);
      o.matrix.copy(at);
      o.matrix.decompose(o.position, o.quaternion, o.scale);
      o.position.y = 0.05;
      o.scale.set(s.along * 3.4, 1, s.wide * 3.4);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    return m;
  }, [mesh, k]);
  // The eye puddles spilling toward the next city (lib/ride.ts eyePuddles): thin and flat, so simpler, and many.
  const pools = useMemo(() => {
    const list = eyePuddles(k);
    if (!list.length) return null;
    const m = new InstancedMesh(blob(2), eyePuddleMaterial(), list.length);
    const under = new InstancedMesh(new PlaneGeometry(1, 1).rotateX(-Math.PI / 2), stain(), list.length);
    m.layers.set(NO_MIRROR_LAYER);
    m.name = 'EyePuddles';
    under.name = 'EyePuddleStains';
    m.frustumCulled = under.frustumCulled = false;
    under.renderOrder = 1;
    const o = new Object3D();
    list.forEach((p, i) => {
      o.position.set(p.x - Math.sin(p.heading) * p.across, 0, -(p.y + Math.cos(p.heading) * p.across));
      o.rotation.set(0, p.heading + p.turn, 0);
      o.scale.set(p.along, p.height, p.wide);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
      o.position.y = 0.045;
      o.scale.set(p.along * 1.7, 1, p.wide * 1.7);
      o.updateMatrix();
      under.setMatrixAt(i, o.matrix);
    });
    return { m, under };
  }, [k]);
  useEffect(
    () => () => {
      mesh.geometry.dispose();
      stains.geometry.dispose();
      pools?.m.geometry.dispose();
      pools?.under.geometry.dispose();
    },
    [mesh, stains, pools]
  );
  useFrame(() => {
    mesh.visible = stains.visible = course.legs[k].placed;
    if (pools) pools.m.visible = pools.under.visible = course.legs[k].placed;
  });
  return (
    <>
      <primitive object={stains} />
      <primitive object={mesh} />
      {pools && <primitive object={pools.under} />}
      {pools && <primitive object={pools.m} />}
    </>
  );
}
