'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { Color, IcosahedronGeometry, InstancedMesh, MeshBasicMaterial, Object3D } from 'three';
import { NO_MIRROR_LAYER } from '@/lib/journey';
import { cityRoadAt, muckSlicks, ride } from '@/lib/ride';

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

export function Muck() {
  const mesh = useMemo(() => {
    const slicks = muckSlicks();
    // (Unlit pure black, so it reflects nothing; and not drawn into the road's mirror, so nothing reflects it as a
    // floating black shape either.)
    const m = new InstancedMesh(blob(), new MeshBasicMaterial({ color: new Color(0, 0, 0) }), slicks.length);
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
  useEffect(() => () => mesh.geometry.dispose(), [mesh]);
  useFrame(() => {
    mesh.visible = ride.transition.placed;
  });
  return <primitive object={mesh} />;
}
