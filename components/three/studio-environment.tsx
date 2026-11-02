'use client';

import { useThree } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { type Material, type Object3D, PMREMGenerator, type Texture, type WebGLRenderer } from 'three';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

let cached: Texture | null = null;

function studioEnvMap(gl: WebGLRenderer) {
  if (!cached) {
    // Procedural softbox room, so nothing is downloaded.
    const pmrem = new PMREMGenerator(gl);
    cached = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    pmrem.dispose();
  }
  return cached;
}

/**
 * Gives a model's own materials glossy studio reflections. Set per material rather than on the scene,
 * so the plaster around it never picks up extra light.
 */
export function useStudioReflections(root: Object3D, intensity = 1) {
  const gl = useThree((s) => s.gl);
  const envMap = useMemo(() => studioEnvMap(gl), [gl]);
  useEffect(() => {
    root.traverse((child) => {
      const material = (child as Object3D & { material?: Material & { envMap?: Texture | null; envMapIntensity?: number } }).material;
      if (material && 'envMapIntensity' in material) {
        material.envMap = envMap;
        // A material can ask for its own strength (the landing's, which mostly don't want the white room).
        material.envMapIntensity = material.userData.envMapIntensity ?? intensity;
        material.needsUpdate = true;
      }
    });
  }, [root, envMap, intensity]);
}
