'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useRef, useState } from 'react';
import type { Group, Material, Mesh, Texture } from 'three';
import { ride } from '@/lib/ride';
import { DRACO_PATH } from './biome';

// The second city (art/build-city2.py), loaded during the ride: it's downloaded once the visitor gets on the bike,
// its shaders compiled and textures uploaded off to the side, and only then marked ready, which is what sets the bike's
// chrome morph going (components/three/ride.tsx). Until the transition places it down the road it stays hidden.
// (Dev: ?city2=<url> loads another model in its place, to try the flow.)
const URL = '/models/city2.glb';
const url = () => (process.env.NODE_ENV === 'development' && new URLSearchParams(window.location.search).get('city2')) || URL;

function CityTwo({ src }: { src: string }) {
  const { scene } = useGLTF(src, DRACO_PATH);
  const group = useRef<Group>(null);
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const world = useThree((s) => s.scene);

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
