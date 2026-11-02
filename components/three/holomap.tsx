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
  Vector2,
  Vector3,
} from 'three';
import { course, ZONES } from '@/lib/course';
import { smoothstep } from '@/lib/journey';
import { ride } from '@/lib/ride';
import { DRACO_PATH } from './biome';

// Pulled up in a city, after the arrival shot, the camera's back on the bike and the rider's gloved hands come up into
// view (art/build-hands.py, hands.glb, carried by the camera) holding a slim projector, from which a see-through
// hologram map opens out: the road back to the green city through every place passed, where you are, and the road on
// into a haze of the next place's colours (to ride on there, picked on the map). Paced by ride.transition.map
// (components/three/ride.tsx).

const PANEL = { w: 0.38, h: 0.27 };
const corner = new Vector3();

/**
 * The places on the map, in its drawing's units (360 by 260), along a road winding up from the bottom left: the green
 * city, the chrome city, the hive, the desert. Each with its star's colours and the colours of its haze, seen from the
 * place before it.
 */
const PLACES = [
  { x: 60, y: 212, star: ['#3dff6a', '#b8ff9a'], haze: ['#3dff6a', '#1fb35a', '#b8ff9a'] },
  { x: 150, y: 152, star: ['#ff7ad0', '#9feeff'], haze: ['#ff7ad0', '#8a7bff', '#5ff0ff'] },
  { x: 236, y: 104, star: ['#ffb84d', '#ff8f9a'], haze: ['#ffb84d', '#ff6f61', '#ffe27a'] },
  { x: 308, y: 50, star: ['#ffcf6a', '#8dff7a'], haze: ['#e8a14a', '#c9762e', '#8dff7a'] },
];
/** The road's curve between two places (a gentle S). */
const leg = (a: (typeof PLACES)[number], b: (typeof PLACES)[number]) =>
  `C${a.x + (b.x - a.x) * 0.45} ${a.y - 4}, ${a.x + (b.x - a.x) * 0.55} ${b.y + 8}, ${b.x} ${b.y}`;

/**
 * The map's drawing, as an SVG (glowing light on nothing: the hologram shader adds the scan lines and flicker). Abstract:
 * where you are (`here`, a zone) is a glowing four-pointed star in that place's colours; where you've been, smaller,
 * dimmer ones, the road back through them lit; where the road goes next, it fades out into a haze of the next place's
 * colours. Nothing past that: it's unknown.
 */
function mapSvg(here: number) {
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
  // Where the road goes next: a drifting haze of the next place's colours that the path fades into.
  const fog = (x: number, y: number, colours: string[]) => `
  <g transform="translate(${x} ${y})" filter="url(#fog)">
    <ellipse cx="-14" cy="6" rx="46" ry="26" fill="${colours[0]}" opacity="0.32"/>
    <ellipse cx="18" cy="-6" rx="40" ry="24" fill="${colours[1]}" opacity="0.3"/>
    <ellipse cx="4" cy="14" rx="34" ry="18" fill="${colours[2]}" opacity="0.26"/>
    <ellipse cx="0" cy="0" rx="58" ry="34" fill="#cfd2ff" opacity="0.12"/>
  </g>`;
  const at = PLACES[here];
  const next = PLACES[here + 1];
  const frame = `
  <defs>
    <filter id="soft" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="0.8"/></filter>
    <filter id="fog" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="11"/></filter>
    <linearGradient id="fadeOn" gradientUnits="userSpaceOnUse" x1="${at.x + 10}" y1="0" x2="${next ? next.x + 8 : at.x + 60}" y2="0"><stop offset="0" stop-color="#ffffff" stop-opacity="0.95"/><stop offset="0.55" stop-color="#ffffff" stop-opacity="0.6"/><stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
    <linearGradient id="trail" gradientUnits="userSpaceOnUse" x1="${PLACES[0].x}" y1="0" x2="${at.x}" y2="0">${PLACES.slice(0, here + 1)
      .map((p, i) => `<stop offset="${here ? i / here : 0}" stop-color="${p.star[0]}"/>`)
      .join('')}</linearGradient>
  </defs>
  <path d="M10 10h22M10 10v22M350 10h-22M350 10v22M10 250h22M10 250v-22M350 250h-22M350 250v-22" stroke="${ink}" stroke-opacity="0.8" stroke-width="2" fill="none"/>
  ${Array.from({ length: 40 }, (_, i) => {
    const h = Math.sin(i * 91.7) * 43758.5453;
    const f = h - Math.floor(h);
    const g = Math.sin(i * 47.3) * 9631.7;
    return `<circle cx="${(20 + f * 320).toFixed(1)}" cy="${(20 + (g - Math.floor(g)) * 220).toFixed(1)}" r="${(0.5 + f * 0.9).toFixed(2)}" fill="${ink}" fill-opacity="${(0.25 + f * 0.4).toFixed(2)}"/>`;
  }).join('')}`;
  // The road travelled, lit, back to the green city; the road on, dotted, fading into the next place's haze.
  const travelled = here
    ? `<path d="M${PLACES[0].x} ${PLACES[0].y} ${PLACES.slice(1, here + 1)
        .map((p, i) => leg(PLACES[i], p))
        .join(' ')}" fill="none" stroke="url(#trail)" stroke-width="3" stroke-linecap="round" opacity="0.9"/>`
    : '';
  const on = next
    ? `${fog(next.x, next.y, next.haze)}
  <path d="M${at.x} ${at.y} ${leg(at, next)}" fill="none" stroke="url(#fadeOn)" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="1.5 8"/>`
    : '';
  const been = PLACES.slice(0, here)
    .map((p, i) => star(p.x, p.y, i === 0 ? 13 : 11, p.star[0], p.star[1], `was${i}`, 0.55))
    .join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 260" width="1024" height="740">${frame}
  ${travelled}
  ${on}
  ${been}
  ${star(at.x, at.y, 24, at.star[0], at.star[1], 'here')}
</svg>`;
}

function useMapTexture(here: number) {
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
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(mapSvg(here))}`;
    return t;
  }, [here]);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
}

/** A see-through hologram: the map's light, scan lines rolling up it, flicker, brighter edges, a faint blue body. */
function hologramMaterial(map: CanvasTexture) {
  return new ShaderMaterial({
    uniforms: {
      uMap: { value: map },
      uTime: { value: 0 },
      uOpen: { value: 0 },
      uBack: { value: 0 },
      uOn: { value: 0 },
      uOnAt: { value: new Vector2(0.5, 0.5) },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D uMap;
      uniform float uTime;
      uniform float uOpen;
      uniform float uBack;
      uniform float uOn;
      uniform vec2 uOnAt;
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
        // The next place, ridden on to from its haze: lit the same way.
        vec2 o = (vUv - uOnAt) / vec2(0.15, 0.2);
        float on = (1.0 - smoothstep(0.6, 1.0, length(o))) * uOn;
        col += vec3(1.0, 0.85, 0.55) * on * (0.25 + 0.75 * c.a);
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
  // (One drawing for each place: where you are, there.)
  const maps = [useMapTexture(0), useMapTexture(1), useMapTexture(2), useMapTexture(3)];
  const material = useMemo(() => hologramMaterial(maps[0]), [maps[0]]);
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
    const here = arrived ? ride.zone : 0;
    material.uniforms.uMap.value = maps[here];
    const next = PLACES[here + 1];
    if (next) (material.uniforms.uOnAt.value as Vector2).set(next.x / 360, 1 - next.y / 260);
    const r = rig.current;
    if (!r) return;
    r.visible = m > 0.3;
    if (!r.visible) {
      ride.mapBack.shown = ride.mapOn.shown = false;
      return;
    }
    // The hands come up from below (rotating up about a point at the chest), then the map opens out.
    const raise = smoothstep(0.35, 0.72, m);
    const open = smoothstep(0.68, 1, m);
    // (Lowered, they turn down about a point below the chest, out of view: art/build-hands.py's pivot.)
    if (holder.current) {
      holder.current.rotation.x = -0.78 * (1 - raise);
      holder.current.position.set(0, -0.6 + 0.004 * Math.sin(state.clock.elapsedTime * 1.3), 0);
    }
    material.uniforms.uTime.value = state.clock.elapsedTime;
    material.uniforms.uOpen.value = open;
    material.uniforms.uBack.value += ((ride.mapBack.hover ? 1 : 0.15 + 0.15 * Math.sin(state.clock.elapsedTime * 3)) - material.uniforms.uBack.value) * 0.15;
    // (The next place breathes too, while it can be ridden on to: its city's way out is known.)
    const onward = arrived && !!next && ZONES[here + 1] !== undefined && !!course.legs[here].end;
    const onGlow = onward ? (ride.mapOn.hover ? 1 : 0.2 + 0.2 * Math.sin(state.clock.elapsedTime * 3 + 1.5)) : 0;
    material.uniforms.uOn.value += (onGlow - material.uniforms.uOn.value) * 0.15;
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
      // Where the green city (the way back) and the next place (on) are on screen, for the buttons over them.
      p.updateWorldMatrix(true, false);
      const onScreen = (target: typeof ride.mapBack, shown: boolean, u0: number, u1: number, v0: number, v1: number) => {
        target.shown = shown;
        if (!shown) return;
        let x0 = Number.POSITIVE_INFINITY;
        let y0 = Number.POSITIVE_INFINITY;
        let x1 = Number.NEGATIVE_INFINITY;
        let y1 = Number.NEGATIVE_INFINITY;
        for (const [u, v] of [
          [u0, v0],
          [u1, v0],
          [u0, v1],
          [u1, v1],
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
        Object.assign(target, { x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
      };
      onScreen(ride.mapBack, arrived && open > 0.95, 0.09, 0.25, 0.07, 0.3);
      const nu = next ? next.x / 360 : 0;
      const nv = next ? 1 - next.y / 260 : 0;
      onScreen(ride.mapOn, onward && open > 0.95, nu - 0.11, nu + 0.11, nv - 0.15, nv + 0.15);
    }
  });

  return (
    // (Shrunk toward the eye, a viewmodel's trick: the same on screen, but in front of the bike's dash, not through it.)
    <group ref={rig} visible={false} scale={0.55}>
      <group ref={holder}>
        {/* (Up a little from where art/build-hands.py holds them, clear of the throttle and higher in the view.) */}
        <group position={[0, 0.66, 0.02]}>
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
