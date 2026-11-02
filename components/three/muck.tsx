'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { CanvasTexture, Color, IcosahedronGeometry, InstancedMesh, Matrix4, MeshBasicMaterial, Object3D, PlaneGeometry } from 'three';
import { NO_MIRROR_LAYER } from '@/lib/journey';
import { cityRoadAt, muckSlicks, ride } from '@/lib/ride';
import { voidGloop } from './void-gloop';

// The slicks of black ooze on the second city's road (lib/ride.ts muckSlicks), raised gooey lumps, dead black for now.
// Drawn in the city's own frame (a child of its group): three's axes, x along the road in, z to its right.

/** A lumpy, flattened blob: an icosphere pushed about by a little noise, its underside flat on the road. */
function blob() {
  const g = new IcosahedronGeometry(1, 3);
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

export function Muck() {
  const mesh = useMemo(() => {
    const slicks = muckSlicks();
    // (A window onto somewhere else, reflecting nothing (components/three/void-gloop.ts); and not drawn into the road's
    // mirror, so nothing reflects it as a floating shape either.)
    const m = new InstancedMesh(blob(), voidGloop(), slicks.length);
    m.layers.set(NO_MIRROR_LAYER);
    m.name = 'Muck';
    m.frustumCulled = false;
    const o = new Object3D();
    slicks.forEach((s, i) => {
      const at = cityRoadAt(s.u);
      // Across the road: to the left of its heading (Blender's frame), so in three's, (-sin, -cos) on x, z.
      o.position.set(at.x - Math.sin(at.heading) * s.across, 0, -(at.y + Math.cos(at.heading) * s.across));
      o.rotation.set(0, at.heading + s.turn, 0);
      o.scale.set(s.along, s.height, s.wide);
      o.updateMatrix();
      m.setMatrixAt(i, o.matrix);
    });
    return m;
  }, []);
  // The stains: flat discs a size larger than each slick, just above the road.
  const stains = useMemo(() => {
    const slicks = muckSlicks();
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
  }, [mesh]);
  useEffect(
    () => () => {
      mesh.geometry.dispose();
      stains.geometry.dispose();
    },
    [mesh, stains]
  );
  useFrame(() => {
    mesh.visible = stains.visible = ride.transition.placed;
  });
  return (
    <>
      <primitive object={stains} />
      <primitive object={mesh} />
    </>
  );
}
