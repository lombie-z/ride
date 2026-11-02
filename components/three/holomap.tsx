'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  AdditiveBlending,
  CanvasTexture,
  DoubleSide,
  type Group,
  type Mesh,
  type MeshStandardMaterial,
  type Object3D,
  PlaneGeometry,
  ShaderMaterial,
  SRGBColorSpace,
} from 'three';
import { smoothstep } from '@/lib/journey';
import { ride } from '@/lib/ride';
import { DRACO_PATH } from './biome';

// Pulled up in the chrome city, after the arrival shot, the camera's back on the bike and the rider's gloved hands
// come up into view (art/build-hands.py, hands.glb, carried by the camera) holding a slim projector, from which a
// see-through hologram map opens out: the route back to the green city, the chrome city where you are, and a road on to
// a question mark. Paced by ride.transition.map (components/three/ride.tsx).

/** The map's drawing, as an SVG (glowing lines on nothing: the hologram shader gives it its light). */
function mapSvg() {
  const glow = '#7ff6ff';
  const violet = '#c69bff';
  const green = '#7dff6a';
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 260" width="1024" height="740">
  <defs>
    <pattern id="g" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="${glow}" stroke-opacity="0.18" stroke-width="0.6"/></pattern>
    <linearGradient id="r" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="${green}"/><stop offset="1" stop-color="${violet}"/></linearGradient>
  </defs>
  <rect x="4" y="4" width="352" height="252" rx="14" fill="url(#g)" stroke="${glow}" stroke-opacity="0.65" stroke-width="1.4"/>
  <path d="M10 10h22M10 10v22M350 10h-22M350 10v22M10 250h22M10 250v-22M350 250h-22M350 250v-22" stroke="${glow}" stroke-width="2.4" fill="none"/>
  <text x="18" y="28" font-family="monospace" font-size="10" letter-spacing="3" fill="${glow}">ROUTE</text>
  <text x="342" y="28" font-family="monospace" font-size="8" letter-spacing="2" fill="${glow}" fill-opacity="0.7" text-anchor="end">SECTOR 02</text>
  <path d="M150 196 C200 214, 278 200, 330 166 L338 238 L144 242 Z" fill="${glow}" fill-opacity="0.1" stroke="${glow}" stroke-opacity="0.35" stroke-width="0.8"/>
  <path d="M62 214 C96 190, 104 160, 138 150 S176 142, 190 132" fill="none" stroke="url(#r)" stroke-width="4" stroke-linecap="round"/>
  <path d="M190 132 C214 110, 232 104, 252 84 S286 54, 304 48" fill="none" stroke="${violet}" stroke-width="3" stroke-linecap="round" stroke-dasharray="2 9"/>
  <g transform="translate(62 214) scale(1.35)" stroke="${green}" fill="none" stroke-width="1.2">
    <path d="M-20 4V-18L-16-30L-12-18V4"/><path d="M-6 4V-30L0-48L6-30V4"/><path d="M11 4V-14L15-24L19-14V4"/>
    <path d="M-3-26h6M-3-18h6M-3-10h6M-18-10h4M13-8h4" stroke-width="2"/>
  </g>
  <g transform="translate(190 132) scale(1.35)" stroke="${glow}" fill="none" stroke-width="1.2">
    <circle r="22" stroke-opacity="0.5"/><circle r="27" stroke-opacity="0.25" stroke-dasharray="3 4"/>
    <path d="M-3 4V-30h6V4"/><ellipse cy="-24" rx="13" ry="3.2"/><ellipse cy="-14" rx="11" ry="3"/><ellipse cy="-4" rx="9" ry="2.8"/><path d="M0-30v-10"/>
  </g>
  <g transform="translate(304 48)">
    <circle r="18" fill="none" stroke="${violet}" stroke-width="1.6"/><circle r="23" fill="none" stroke="${violet}" stroke-opacity="0.4" stroke-dasharray="2 5"/>
    <text y="7" text-anchor="middle" font-family="sans-serif" font-weight="700" font-size="21" fill="${violet}">?</text>
  </g>
  <g font-family="monospace" font-size="10" letter-spacing="1.6" fill="${glow}">
    <text x="62" y="248" text-anchor="middle" fill="${green}">GREEN CITY</text>
    <text x="190" y="182" text-anchor="middle">CHROME CITY</text>
    <text x="190" y="195" text-anchor="middle" font-size="8" fill-opacity="0.75">YOU ARE HERE</text>
    <text x="304" y="84" text-anchor="middle" font-size="8" fill="${violet}">UNCHARTED</text>
  </g>
</svg>`;
}

function useMapTexture() {
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 1024;
    canvas.height = 740;
    const t = new CanvasTexture(canvas);
    t.colorSpace = SRGBColorSpace;
    const image = new Image();
    image.onload = () => {
      (canvas.getContext('2d') as CanvasRenderingContext2D).drawImage(image, 0, 0, canvas.width, canvas.height);
      t.needsUpdate = true;
    };
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(mapSvg())}`;
    return t;
  }, []);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

/** A see-through hologram: the map's light, scan lines rolling up it, flicker, brighter edges, a faint blue body. */
function hologramMaterial(map: CanvasTexture) {
  return new ShaderMaterial({
    uniforms: { uMap: { value: map }, uTime: { value: 0 }, uOpen: { value: 0 } },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D uMap;
      uniform float uTime;
      uniform float uOpen;
      varying vec2 vUv;
      float hash(float n) { return fract(sin(n) * 43758.5453); }
      void main() {
        // A little chromatic split and a wobble line drifting up through it.
        float wob = sin(vUv.y * 140.0 + uTime * 9.0) * 0.0012 + step(0.985, fract(vUv.y * 0.5 - uTime * 0.18)) * 0.006;
        vec4 c = texture2D(uMap, vUv + vec2(wob, 0.0));
        float r = texture2D(uMap, vUv + vec2(wob + 0.0025, 0.0)).r;
        float b = texture2D(uMap, vUv + vec2(wob - 0.0025, 0.0)).b;
        vec3 col = vec3(r, c.g, b) * c.a;
        float scan = 0.72 + 0.28 * sin(vUv.y * 620.0 - uTime * 12.0);
        float flicker = 0.9 + 0.1 * hash(floor(uTime * 24.0));
        // The projection's body: faint, brighter toward its edges.
        vec2 e = min(vUv, 1.0 - vUv);
        float rim = 1.0 - smoothstep(0.0, 0.06, min(e.x, e.y));
        vec3 body = vec3(0.25, 0.55, 0.85) * (0.07 + 0.25 * rim);
        // Opening out from a line: the leading edges glow.
        float sweep = smoothstep(0.0, 0.04, uOpen - abs(vUv.y - 0.5) * 2.0);
        vec3 lightOut = (col * 1.6 * scan + body) * flicker * sweep;
        gl_FragColor = vec4(lightOut, 1.0);
        #include <colorspace_fragment>
      }`,
    transparent: true,
    blending: AdditiveBlending,
    depthWrite: false,
    depthTest: false,
    side: DoubleSide,
    toneMapped: false,
    fog: false,
  });
}

/** The hands (if the model's been built: the file's checked for first). */
function Hands({ onAnchor }: { onAnchor: (anchor: Object3D | null) => void }) {
  const { scene } = useGLTF('/models/hands.glb', DRACO_PATH);
  useEffect(() => {
    scene.traverse((o) => {
      const m = (o as Mesh).material as MeshStandardMaterial | undefined;
      if (!m) return;
      (o as Mesh).renderOrder = 20;
      if (m.name === 'HandsEmitter') {
        m.emissiveIntensity = 4;
        m.toneMapped = false;
      }
    });
    onAnchor(scene.getObjectByName('HologramAnchor') ?? null);
  }, [scene, onAnchor]);
  return <primitive object={scene} />;
}

export function HoloMap() {
  const camera = useThree((s) => s.camera);
  const rig = useRef<Group>(null);
  const holder = useRef<Group>(null);
  const panel = useRef<Mesh>(null);
  const map = useMapTexture();
  const material = useMemo(() => hologramMaterial(map), [map]);
  const geometry = useMemo(() => new PlaneGeometry(0.46, 0.33), []);
  const [hands, setHands] = useState(false);
  const anchor = useRef<Object3D | null>(null);

  // The rig rides with the camera.
  useEffect(() => {
    const r = rig.current;
    if (!r) return;
    camera.add(r);
    return () => {
      camera.remove(r);
    };
  }, [camera]);
  useEffect(() => {
    fetch('/models/hands.glb', { method: 'HEAD' })
      .then((r) => r.ok && setHands(true))
      .catch(() => {});
  }, []);

  useFrame((state) => {
    const m = ride.transition.map;
    const r = rig.current;
    if (!r) return;
    r.visible = m > 0.3;
    if (!r.visible) return;
    // The hands come up from below (rotating up about a point at the chest), then the map opens out.
    const raise = smoothstep(0.35, 0.72, m);
    const open = smoothstep(0.68, 1, m);
    if (holder.current) {
      holder.current.rotation.x = -0.75 * (1 - raise);
      holder.current.position.set(0, -0.35 * (1 - raise) + 0.006 * Math.sin(state.clock.elapsedTime * 1.3), 0);
    }
    material.uniforms.uTime.value = state.clock.elapsedTime;
    material.uniforms.uOpen.value = open;
    const p = panel.current;
    if (p) {
      p.visible = open > 0.001;
      // Above the projector's emitter, tilted back toward the eye, opening from a sliver.
      const a = anchor.current;
      if (a) {
        a.updateWorldMatrix(true, false);
        p.position.set(0, 0.17, 0);
        a.getWorldPosition(p.position);
        r.worldToLocal(p.position);
        p.position.y += 0.15;
      } else p.position.set(0, -0.05, -0.62);
      p.rotation.set(-0.08, 0, 0);
      p.scale.set(0.25 + 0.75 * smoothstep(0, 0.4, open), Math.max(0.02, open), 1);
    }
  });

  return (
    <group ref={rig} visible={false}>
      <group ref={holder}>
        {hands && (
          <Suspense fallback={null}>
            <Hands
              onAnchor={(a) => {
                anchor.current = a;
              }}
            />
          </Suspense>
        )}
      </group>
      <mesh ref={panel} geometry={geometry} material={material} renderOrder={21} frustumCulled={false} />
    </group>
  );
}
