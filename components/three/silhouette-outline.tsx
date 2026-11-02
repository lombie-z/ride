'use client';

import { useFBO } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import { Color, type Mesh, MeshBasicMaterial, type Object3D, ShaderMaterial, Vector2, Vector3 } from 'three';

// Sticker-style outline: renders the model's silhouette into a mask each frame, then draws a dilated
// white band with a thin dark rim behind it. Follows rotation and animation because it is the real silhouette.
const vertexShader = /* glsl */ `
  uniform float uDepth;
  varying vec2 vUv;
  void main() {
    vUv = uv;
    gl_Position = vec4(position.xy, uDepth, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  uniform sampler2D uMask;
  uniform vec2 uTexel;
  uniform float uWidth;
  uniform float uRim;
  uniform vec3 uColor;
  uniform vec3 uRimColor;
  uniform float uOpacity;
  varying vec2 vUv;
  const int ANGLES = 40;
  const int RINGS = 12;
  bool near(float reach) {
    // Coarse pass: most pixels are nowhere near the silhouette, so skip the full search for them.
    for (int a = 0; a < 16; a++) {
      float t = 6.2831853 * float(a) / 16.0;
      vec2 dir = vec2(cos(t), sin(t)) * uTexel;
      if (texture2D(uMask, vUv + dir * reach).r > 0.5 || texture2D(uMask, vUv + dir * reach * 0.5).r > 0.5) return true;
    }
    return false;
  }
  void main() {
    if (texture2D(uMask, vUv).r > 0.5) discard;
    float reach = uWidth + uRim;
    if (!near(reach)) discard;
    float dist = reach + 1.0;
    for (int r = 1; r <= RINGS; r++) {
      float radius = reach * float(r) / float(RINGS);
      for (int a = 0; a < ANGLES; a++) {
        float t = 6.2831853 * (float(a) + 0.5 * float(r)) / float(ANGLES);
        if (texture2D(uMask, vUv + vec2(cos(t), sin(t)) * radius * uTexel).r > 0.5) {
          dist = min(dist, radius);
        }
      }
      if (dist <= reach) break;
    }
    if (dist > reach) discard;
    float edge = reach / float(RINGS);
    float rim = smoothstep(uWidth - edge * 0.5, uWidth + edge * 0.5, dist);
    float alpha = 1.0 - smoothstep(reach - edge, reach, dist);
    gl_FragColor = vec4(mix(uColor, uRimColor, rim), alpha * uOpacity);
  }
`;

const projected = new Vector3();

interface SilhouetteOutlineProps {
  /** Objects whose silhouette gets the outline. */
  target: Object3D;
  /** Objects hidden from the silhouette (left un-outlined). */
  exclude: (object: Object3D) => boolean;
  /** World-space point the sticker sits at in depth: things nearer pass in front of the band, farther pass behind. */
  depthAt: Vector3;
  /** Outline widths in CSS pixels. */
  width?: number;
  rim?: number;
  color?: string;
  rimColor?: string;
  /** Optional 0-1 visibility, read every frame. */
  fade?: () => number;
}

export function SilhouetteOutline({ target, exclude, depthAt, width = 12, rim = 2.5, color = '#ffffff', rimColor = '#2f2a27', fade }: SilhouetteOutlineProps) {
  const dpr = useThree((s) => s.viewport.dpr);
  const mask = useFBO();
  const quad = useRef<Mesh>(null);
  const maskMaterial = useMemo(() => new MeshBasicMaterial({ color: 'white' }), []);
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms: {
          uMask: { value: mask.texture },
          uDepth: { value: 0.999 },
          uTexel: { value: new Vector2() },
          uWidth: { value: 0 },
          uRim: { value: 0 },
          uColor: { value: new Color(color) },
          uRimColor: { value: new Color(rimColor) },
          uOpacity: { value: 1 },
        },
        transparent: true,
        depthTest: true,
        depthWrite: false,
      }),
    [mask, color, rimColor]
  );

  // After the scene's own animation (priority 0), before drei's View draws it (priority 1).
  useFrame((state) => {
    const { gl, scene, camera } = state;
    const visibility = fade ? fade() : 1;
    if (quad.current) quad.current.visible = visibility > 0.001;
    material.uniforms.uOpacity.value = visibility;
    if (visibility <= 0.001) return;
    const hidden: Object3D[] = [];
    scene.traverse((o) => {
      if (o.visible && (o === quad.current || (o !== target && exclude(o)))) {
        o.visible = false;
        hidden.push(o);
      }
    });
    const previousOverride = scene.overrideMaterial;
    const previousTarget = gl.getRenderTarget();
    scene.overrideMaterial = maskMaterial;
    gl.setRenderTarget(mask);
    gl.setClearColor(0x000000, 0);
    gl.clear();
    gl.render(scene, camera);
    gl.setRenderTarget(previousTarget);
    scene.overrideMaterial = previousOverride;
    for (const o of hidden) o.visible = true;

    material.uniforms.uDepth.value = projected.copy(depthAt).project(camera).z;
    material.uniforms.uTexel.value.set(1 / mask.width, 1 / mask.height);
    material.uniforms.uWidth.value = width * dpr;
    material.uniforms.uRim.value = rim * dpr;
  }, 0.5);

  return (
    <mesh ref={quad} material={material} frustumCulled={false} renderOrder={-10}>
      <planeGeometry args={[2, 2]} />
    </mesh>
  );
}
