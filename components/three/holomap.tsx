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
  Vector3,
} from 'three';
import { smoothstep } from '@/lib/journey';
import { ride } from '@/lib/ride';
import { DRACO_PATH } from './biome';

// Pulled up in the chrome city, after the arrival shot, the camera's back on the bike and the rider's gloved hands
// come up into view (art/build-hands.py, hands.glb, carried by the camera) holding a slim projector, from which a
// see-through hologram map opens out: the route back to the green city, the chrome city where you are, and a road on to
// a question mark. Paced by ride.transition.map (components/three/ride.tsx).

const PANEL = { w: 0.38, h: 0.27 };
const corner = new Vector3();

/**
 * The map's drawing, as an SVG (glowing light on nothing: the hologram shader adds the scan lines and flicker). Abstract:
 * where you are is a glowing four-pointed star in that city's colours; where you've been, a smaller, dimmer one; where
 * the road goes next, a bank of cloud with the next place's colours glowing through its gaps. At the start, in the green
 * city, the next place is the chrome city (its pink, violet and cyan peek through); arrived there, the next is unknown
 * (gold and coral, a hint of somewhere warmer).
 */
function mapSvg(mode: 'start' | 'arrived') {
  const ink = '#7ff6ff';
  const star = (x: number, y: number, r: number, a: string, b: string, id: string, glow = 1) => `
  <g transform="translate(${x} ${y})">
    <circle r="${r * 1.9}" fill="url(#${id}Halo)" opacity="${0.8 * glow}"/>
    <path d="M0 ${-r} C${r * 0.12} ${-r * 0.22} ${r * 0.22} ${-r * 0.12} ${r} 0 C${r * 0.22} ${r * 0.12} ${r * 0.12} ${r * 0.22} 0 ${r} C${-r * 0.12} ${r * 0.22} ${-r * 0.22} ${r * 0.12} ${-r} 0 C${-r * 0.22} ${-r * 0.12} ${-r * 0.12} ${-r * 0.22} 0 ${-r} Z"
      fill="url(#${id}Fill)" filter="url(#soft)" opacity="${glow}"/>
    <path d="M0 ${-r} C${r * 0.12} ${-r * 0.22} ${r * 0.22} ${-r * 0.12} ${r} 0 C${r * 0.22} ${r * 0.12} ${r * 0.12} ${r * 0.22} 0 ${r} C${-r * 0.12} ${r * 0.22} ${-r * 0.22} ${r * 0.12} ${-r} 0 C${-r * 0.22} ${-r * 0.12} ${-r * 0.12} ${-r * 0.22} 0 ${-r} Z"
      fill="none" stroke="#ffffff" stroke-opacity="${0.8 * glow}" stroke-width="0.8"/>
  </g>
  <defs>
    <radialGradient id="${id}Halo"><stop offset="0" stop-color="${a}" stop-opacity="0.55"/><stop offset="1" stop-color="${a}" stop-opacity="0"/></radialGradient>
    <radialGradient id="${id}Fill"><stop offset="0" stop-color="#ffffff"/><stop offset="0.35" stop-color="${b}"/><stop offset="1" stop-color="${a}"/></radialGradient>
  </defs>`;
  // A bank of cloud, its gaps showing the colours behind (blobs of them under a cloud mask with holes).
  const clouds = (x: number, y: number, colours: string[]) => `
  <g transform="translate(${x} ${y})">
    <g filter="url(#blur)">
      ${colours.map((c, i) => `<circle cx="${-30 + i * 28}" cy="${(i % 2) * 10 - 2}" r="24" fill="${c}"/>`).join('')}
    </g>
    <g fill="#d8d2ff" fill-opacity="0.7" filter="url(#soft)">
      <circle cx="-34" cy="6" r="15"/><circle cx="-16" cy="-6" r="18"/><circle cx="6" cy="-12" r="16"/><circle cx="26" cy="-2" r="17"/>
      <circle cx="40" cy="10" r="12"/><circle cx="-4" cy="10" r="16"/><circle cx="18" cy="14" r="13"/><circle cx="-24" cy="16" r="11"/>
    </g>
    <g fill="#04050a">
      <ellipse cx="-10" cy="3" rx="9" ry="5"/><ellipse cx="18" cy="5" rx="8" ry="4.5"/><ellipse cx="4" cy="-5" rx="6" ry="3.5"/>
    </g>
    <g filter="url(#soft)" opacity="0.95">
      <ellipse cx="-10" cy="3" rx="9" ry="5" fill="${colours[0]}"/><ellipse cx="18" cy="5" rx="8" ry="4.5" fill="${colours[1]}"/><ellipse cx="4" cy="-5" rx="6" ry="3.5" fill="${colours[2]}"/>
    </g>
  </g>`;
  const frame = `
  <defs>
    <filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="0.8"/></filter>
    <filter id="blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="5"/></filter>
    <linearGradient id="trail" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#7dff6a"/><stop offset="1" stop-color="#ff8ad8"/></linearGradient>
  </defs>
  <path d="M10 10h22M10 10v22M350 10h-22M350 10v22M10 250h22M10 250v-22M350 250h-22M350 250v-22" stroke="${ink}" stroke-opacity="0.8" stroke-width="2" fill="none"/>
  ${Array.from({ length: 40 }, (_, i) => {
    const h = Math.sin(i * 91.7) * 43758.5453;
    const f = h - Math.floor(h);
    const g = Math.sin(i * 47.3) * 9631.7;
    return `<circle cx="${(20 + f * 320).toFixed(1)}" cy="${(20 + (g - Math.floor(g)) * 220).toFixed(1)}" r="${(0.5 + f * 0.9).toFixed(2)}" fill="${ink}" fill-opacity="${(0.25 + f * 0.4).toFixed(2)}"/>`;
  }).join('')}`;
  if (mode === 'start')
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 260" width="1024" height="740">${frame}
  <path d="M76 190 C130 176, 160 150, 205 124 S262 92, 282 84" fill="none" stroke="#c69bff" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="1.5 8" opacity="0.85"/>
  ${star(72, 194, 24, '#3dff6a', '#b8ff9a', 'here')}
  ${clouds(290, 74, ['#ff7ad0', '#8a7bff', '#5ff0ff'])}
</svg>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 260" width="1024" height="740">${frame}
  <path d="M62 212 C100 190, 120 160, 160 146 S186 140, 196 134" fill="none" stroke="url(#trail)" stroke-width="3" stroke-linecap="round" opacity="0.9"/>
  <path d="M206 124 C232 102, 250 92, 268 80 S290 66, 296 62" fill="none" stroke="#ffc07a" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="1.5 8" opacity="0.85"/>
  ${star(60, 212, 13, '#3dff6a', '#b8ff9a', 'was', 0.55)}
  ${star(198, 132, 24, '#ff7ad0', '#9feeff', 'here')}
  ${clouds(300, 56, ['#ffb84d', '#ff6f61', '#ffe27a'])}
</svg>`;
}

function useMapTexture(mode: 'start' | 'arrived') {
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
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(mapSvg(mode))}`;
    return t;
  }, [mode]);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

/** A see-through hologram: the map's light, scan lines rolling up it, flicker, brighter edges, a faint blue body. */
function hologramMaterial(map: CanvasTexture) {
  return new ShaderMaterial({
    uniforms: { uMap: { value: map }, uTime: { value: 0 }, uOpen: { value: 0 }, uBack: { value: 0 } },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D uMap;
      uniform float uTime;
      uniform float uOpen;
      uniform float uBack;
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
        // The green city's way back, lit up when pointed at (or focused).
        vec2 g = (vUv - vec2(0.167, 0.185)) / vec2(0.08, 0.12);
        float back = (1.0 - smoothstep(0.7, 1.0, length(g))) * uBack;
        col += vec3(0.45, 1.0, 0.4) * back * (0.35 + 0.65 * c.a);
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
  const startMap = useMapTexture('start');
  const arrivedMap = useMapTexture('arrived');
  const material = useMemo(() => hologramMaterial(arrivedMap), [arrivedMap]);
  const geometry = useMemo(() => new PlaneGeometry(PANEL.w, PANEL.h), []);
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
    // Arrived in the chrome city, its map; otherwise the glance at the start, in the green city.
    const arrived = ride.transition.arrived;
    const m = arrived ? ride.transition.map : ride.preview;
    material.uniforms.uMap.value = arrived ? arrivedMap : startMap;
    const r = rig.current;
    if (!r) return;
    r.visible = m > 0.3;
    if (!r.visible) {
      ride.mapBack.shown = false;
      return;
    }
    // The hands come up from below (rotating up about a point at the chest), then the map opens out.
    const raise = smoothstep(0.35, 0.72, m);
    const open = smoothstep(0.68, 1, m);
    // (Lowered, they turn down about a point below the chest, out of view: art/build-hands.py's pivot.)
    if (holder.current) {
      holder.current.rotation.x = -0.62 * (1 - raise);
      holder.current.position.set(0, -0.6 + 0.004 * Math.sin(state.clock.elapsedTime * 1.3), 0);
    }
    material.uniforms.uTime.value = state.clock.elapsedTime;
    material.uniforms.uOpen.value = open;
    material.uniforms.uBack.value += ((ride.mapBack.hover ? 1 : 0.15 + 0.15 * Math.sin(state.clock.elapsedTime * 3)) - material.uniforms.uBack.value) * 0.15;
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
        p.position.y += PANEL.h / 2 + 0.012;
      } else p.position.set(0, -0.05, -0.62);
      p.rotation.set(-0.08, 0, 0);
      p.scale.set(0.25 + 0.75 * smoothstep(0, 0.4, open), Math.max(0.02, open), 1);
      // Where the green city (the way back) is on screen, for the button over it.
      const mb = ride.mapBack;
      mb.shown = arrived && open > 0.95;
      if (mb.shown) {
        p.updateWorldMatrix(true, false);
        let x0 = Number.POSITIVE_INFINITY;
        let y0 = Number.POSITIVE_INFINITY;
        let x1 = Number.NEGATIVE_INFINITY;
        let y1 = Number.NEGATIVE_INFINITY;
        for (const [u, v] of [
          [0.09, 0.07],
          [0.25, 0.07],
          [0.09, 0.3],
          [0.25, 0.3],
        ]) {
          corner.set((u - 0.5) * PANEL.w, (v - 0.5) * PANEL.h, 0);
          p.localToWorld(corner).project(state.camera);
          const x = (corner.x * 0.5 + 0.5) * state.size.width;
          const y = (-corner.y * 0.5 + 0.5) * state.size.height;
          x0 = Math.min(x0, x);
          x1 = Math.max(x1, x);
          y0 = Math.min(y0, y);
          y1 = Math.max(y1, y);
        }
        Object.assign(mb, { x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
      }
    }
  });

  return (
    <group ref={rig} visible={false}>
      <group ref={holder}>
        <group position={[0, 0.6, 0]}>
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
      </group>
      <mesh ref={panel} geometry={geometry} material={material} renderOrder={21} frustumCulled={false} />
    </group>
  );
}
