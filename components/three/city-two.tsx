'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useRef, useState } from 'react';
import type { Group, Material, Mesh, MeshStandardMaterial, Texture } from 'three';
import { ride, road } from '@/lib/ride';
import { AT, sunsetEnvMap } from './bike';
import { DRACO_PATH } from './biome';

// The second city (art/build-city2.py), loaded during the ride: it's downloaded once the visitor gets on the bike,
// its shaders compiled and textures uploaded off to the side, and only then marked ready, which is what sets the bike's
// chrome morph and the change of sky going (components/three/ride.tsx), which places it down the road ahead, its own
// road taking over from the endless one (lib/ride.ts cityRoadAt).
// (Dev: ?city2=<url> loads another model in its place, to try the flow.)
const URL = '/models/city2.glb';
const url = () => (process.env.NODE_ENV === 'development' && new URLSearchParams(window.location.search).get('city2')) || URL;

function CityTwo({ src }: { src: string }) {
  const { scene } = useGLTF(src, DRACO_PATH);
  const group = useRef<Group>(null);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const world = useThree((s) => s.scene);

  // Its materials: the sunset in their reflections; the lit glass, lamps, screen and sun past white for the bloom; the
  // sun itself clear of the haze, far out.
  useEffect(() => {
    const env = sunsetEnvMap(gl);
    scene.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh) return;
      const m = mesh.material as MeshStandardMaterial;
      m.envMap = env;
      m.envMapIntensity = 1.2;
      if (/^City2(Glass|GlassWarm|Lamp|Screen|Sun)$/.test(m.name)) {
        m.emissiveIntensity = m.name === 'City2Sun' ? 14 : m.name === 'City2Screen' ? 3 : 4;
        m.toneMapped = false;
      }
      if (m.name === 'City2Sun') m.fog = false;
      m.needsUpdate = true;
    });
  }, [scene, gl]);

  useEffect(() => {
    let live = true;
    const g = group.current;
    if (!g) return;
    // Compile its programs against the real scene's lights, in the background, then upload its textures; drawn
    // nowhere yet.
    g.visible = true;
    const textures = new Set<Texture>();
    scene.traverse((o) => {
      const m = (o as Mesh).material as (Material & Record<string, unknown>) | undefined;
      for (const v of Object.values(m ?? {})) if ((v as Texture)?.isTexture) textures.add(v as Texture);
    });
    gl.compileAsync(g, camera, world)
      .catch(() => {})
      .then(() => {
        if (!live) return;
        for (const t of textures) gl.initTexture(t);
        g.visible = false;
        ride.secondCity.ready = true;
      });
    return () => {
      live = false;
      ride.secondCity.ready = false;
    };
  }, [scene, gl, camera, world]);

  // Placed where the ride's change begins, turned to run on from the endless road (local +x along it).
  useFrame(() => {
    const g = group.current;
    const tr = ride.transition;
    if (!g || !ride.secondCity.ready) return;
    g.visible = tr.placed;
    if (!tr.placed) return;
    g.position.set(AT[0], AT[1], AT[2]).addScaledVector(road.ahead, tr.at);
    g.rotation.set(0, road.yaw, 0);
  });

  return (
    <group ref={group} visible={false}>
      <primitive object={scene} />
    </group>
  );
}

/** Starts loading the second city once the visitor's on the bike (if it's been built: the file's checked for first). */
export function CityTwoLoader() {
  const [src, setSrc] = useState<string | null>(null);
  const asked = useRef(false);
  useFrame(() => {
    if (asked.current || ride.mount < 0.5) return;
    asked.current = true;
    const target = url();
    fetch(target, { method: 'HEAD' })
      .then((r) => r.ok && setSrc(target))
      .catch(() => {});
  });
  return src ? (
    <Suspense fallback={null}>
      <CityTwo src={src} />
    </Suspense>
  ) : null;
}
