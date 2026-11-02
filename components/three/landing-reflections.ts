import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import {
  CubeCamera,
  HalfFloatType,
  type Material,
  type Mesh,
  type MeshPhysicalMaterial,
  type Object3D,
  PMREMGenerator,
  type Texture,
  WebGLCubeRenderTarget,
} from 'three';
import { journey, landingAt } from '@/lib/journey';

// Real reflections for the landing's foreground: once the camera has arrived, the world around it (sky, sun, fall,
// cliffs, lake) is captured from the camera's place into a cube map and prefiltered, and the named materials reflect
// that instead of the white studio room the clay hero uses. Glossy, wet surfaces then show the scene itself. The
// foreground is hidden while capturing, so it doesn't reflect itself. The six views are spread over six frames, and the
// result is the same kind and size of map as the studio's, so the swap needs no shader rebuild; it starts once the
// scroll comes to rest there: no hitch on arrival.

const FOREGROUND = ['LandingReeds', 'LandingPads', 'LandingFrog', 'LandingLilies', 'LandingPebbles', 'LandingDew'];
const isForeground = (o: Object3D) => FOREGROUND.some((name) => o.name.startsWith(name) || o.parent?.name.startsWith(name));

export function useLandingReflections(root: Object3D, materialNames: string[], intensity = 1) {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  const capture = useRef<{ cube: CubeCamera; target: WebGLCubeRenderTarget; face: number } | null>(null);
  const env = useRef<Texture | null>(null);
  const still = useRef({ frame: -1, since: 0 });

  useFrame((state) => {
    if (env.current) return;
    // Only once the scroll has come to rest at the landing, so the capture never costs a frame mid-scroll.
    const s = still.current;
    if (Math.abs(journey.frame - s.frame) > 0.01) {
      s.frame = journey.frame;
      s.since = state.clock.elapsedTime;
    }
    if (landingAt(journey.frame) < 0.97 || state.clock.elapsedTime - s.since < 0.3) return;
    if (!capture.current) {
      const target = new WebGLCubeRenderTarget(256, { type: HalfFloatType });
      const cube = new CubeCamera(0.1, 1000, target);
      cube.position.copy(state.camera.position);
      // (Set the six cameras' orientations up, as CubeCamera.update would on its first call.)
      cube.coordinateSystem = gl.coordinateSystem;
      cube.updateCoordinateSystem();
      cube.updateMatrixWorld();
      capture.current = { cube, target, face: 0 };
    }
    const c = capture.current;
    const hidden: Object3D[] = [];
    root.traverse((o) => {
      if ((o as Mesh).isMesh && o.visible && isForeground(o)) {
        o.visible = false;
        hidden.push(o);
      }
    });
    // One face a frame.
    const previous = gl.getRenderTarget();
    gl.setRenderTarget(c.target, c.face);
    gl.render(scene, c.cube.children[c.face] as never);
    gl.setRenderTarget(previous);
    for (const o of hidden) o.visible = true;
    if (++c.face < 6) return;

    const pmrem = new PMREMGenerator(gl);
    env.current = pmrem.fromCubemap(c.target.texture).texture;
    pmrem.dispose();
    c.target.dispose();
    root.traverse((o) => {
      const material = (o as Mesh).material as Material | undefined;
      if (material && materialNames.includes(material.name)) {
        const physical = material as MeshPhysicalMaterial;
        physical.envMap = env.current;
        physical.envMapIntensity = intensity;
      }
    });
  });

  useEffect(() => () => env.current?.dispose(), []);
}
