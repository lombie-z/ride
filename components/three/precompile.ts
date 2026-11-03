import { type Camera, type Object3D, type Scene, type WebGLRenderer, WebGLRenderTarget } from 'three';

let linear: WebGLRenderTarget | null = null;

/**
 * Compiles an object's programs ahead of drawing it, in the background, against `scene`'s lights: as it'll be drawn,
 * into the post's linear buffer (components/three/effects.tsx). (Compiled for the canvas's sRGB instead, every one was
 * compiled again on first sight, stalling that frame: 100 to 300 ms as a bike's morph began.)
 */
export function precompile(gl: WebGLRenderer, object: Object3D, camera: Camera, scene: Scene) {
  linear ??= new WebGLRenderTarget(1, 1);
  const before = gl.getRenderTarget();
  gl.setRenderTarget(linear);
  const done = gl.compileAsync(object, camera, scene);
  gl.setRenderTarget(before);
  return done;
}

