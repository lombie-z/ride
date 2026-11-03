'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  CanvasTexture,
  CatmullRomCurve3,
  type Group,
  type Mesh,
  type MeshStandardMaterial,
  type Object3D,
  PlaneGeometry,
  SRGBColorSpace,
  TubeGeometry,
  Vector3,
} from 'three';
import { course, ZONES } from '@/lib/course';
import { smoothstep } from '@/lib/journey';
import { ride } from '@/lib/ride';
import { DRACO_PATH } from './biome';
import { holoShared, MARKER, markerMaterial, panelMaterial, roadMaterial, terrainMaterial } from './holomap-materials';

// Pulled up in a city, after the arrival shot, the camera's back on the bike and the rider's gloved hands come up into
// view (art/build-hands.py, hands.glb, carried by the camera) holding a slim projector, over which a black terminal
// powers on: the land in wireframe floating on it, turning slowly, in the zone's one phosphor. The road back to the green
// city through every place passed, a reticle where you are, and the road on to a block of static (to ride on there, picked
// on the map: it locks on when pointed at). Paced by ride.transition.map (components/three/ride.tsx).

const PANEL = { w: 0.38, h: 0.27 };
/** The land's size on it, and how far it's tipped toward the eye (flat, at 0). */
const LAND = { w: 0.28, d: 0.19, tilt: 0.92 };
const view = new Vector3();
const corner = new Vector3();

/**
 * The places on the map, in its drawing's units (360 by 260), along a road winding up from the bottom left: the green
 * city, the chrome city, the hive, the desert. Each with its phosphor.
 */
const PLACES = [
  { x: 60, y: 212, accent: '#3dff6a' },
  { x: 150, y: 152, accent: '#6ff2ff' },
  { x: 236, y: 104, accent: '#ffb02e' },
  { x: 308, y: 50, accent: '#ff6a1f' },
];

/** The land's height at a point on the map. */
function landHeight(x: number, y: number) {
  const n = Math.sin(x * 0.031 + 1.3) * Math.cos(y * 0.043 + 0.7) + 0.55 * Math.sin(x * 0.071 + y * 0.053 + 2.1) + 0.3 * Math.sin(x * 0.13 - y * 0.11 + 0.4);
  return 0.014 * n;
}
/** A point on the map, on the land (and a little over it). */
const onLand = (x: number, y: number, lift = 0) => new Vector3((x / 360 - 0.5) * LAND.w, landHeight(x, y) + lift, (y / 260 - 0.5) * LAND.d);

function landGeometry() {
  const g = new PlaneGeometry(LAND.w, LAND.d, 90, 62);
  g.rotateX(-Math.PI / 2);
  const position = g.attributes.position;
  for (let i = 0; i < position.count; i++) {
    const x = (position.getX(i) / LAND.w + 0.5) * 360;
    const y = (position.getZ(i) / LAND.d + 0.5) * 260;
    position.setY(i, landHeight(x, y));
  }
  return g;
}

/** The whole road, over the land, and how far along it (0 to 1) each place is. */
function roadGeometry() {
  const points: Vector3[] = [];
  for (let k = 0; k < PLACES.length - 1; k++) {
    const a = PLACES[k];
    const b = PLACES[k + 1];
    for (let i = 0; i < 16; i++) {
      // (A gentle S between them: the road's bezier, eased across and held to its ends.)
      const t = i / 16;
      const c = t * t * (3 - 2 * t);
      const bow = Math.sin(t * Math.PI * 2) * 7;
      points.push(onLand(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * c + bow, 0.004));
    }
  }
  const last = PLACES[PLACES.length - 1];
  points.push(onLand(last.x, last.y, 0.004));
  const curve = new CatmullRomCurve3(points);
  const lengths = curve.getLengths(400);
  const total = lengths[lengths.length - 1];
  const at = PLACES.map((_, k) => lengths[Math.round((k * 16 * 400) / (points.length - 1))] / total);
  return { geometry: new TubeGeometry(curve, 240, 0.0028, 5, false), at };
}

/**
 * The terminal's readouts, as an SVG (its light on nothing: its shader adds the glass, the rest): big enough to read
 * through the pixel look, so few.
 */
function readoutSvg(here: number) {
  const ink = PLACES[here].accent;
  const name = ZONES[here].id.toUpperCase();
  const ticks = (n: number, at: (i: number) => string) => Array.from({ length: n }, (_, i) => at(i)).join('');
  // (Its code, rolling on with the place: made up.)
  const code = (0x3a7f + here * 0x1d3).toString(16).toUpperCase();
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 360 260" width="1024" height="740">
  <g font-family="ui-monospace, Menlo, monospace" font-weight="700" fill="${ink}">
    <text x="20" y="35" font-size="22">0${here + 1}<tspan fill-opacity="0.55">//</tspan>${name}</text>
    <text x="330" y="247" font-size="15" text-anchor="end" fill-opacity="0.9">${code}</text>
  </g>
  <g stroke="${ink}" fill="none">
    <path d="M20 44H150" stroke-width="2.4"/>
    <path d="${ticks(15, (i) => `M12 ${70 + i * 10}h${i % 5 === 0 ? 9 : 4}`)}" stroke-width="1.8" stroke-opacity="0.8"/>
  </g>
  <g fill="${ink}">
    ${ticks(5, (i) => `<rect x="${268 + i * 9}" y="${32 - (i + 1) * 4}" width="6" height="${(i + 1) * 4}" fill-opacity="${i < 4 - (here % 2) ? 1 : 0.25}"/>`)}
  </g>
  <g fill="#ff2238">
    ${ticks(7, (i) => `<path d="M${54 + i * 11} 250l6 -11h5l-6 11z"/>`)}
  </g>
</svg>`;
}

function useReadoutTexture(here: number) {
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
    image.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(readoutSvg(here))}`;
    return t;
  }, [here]);
  useEffect(() => () => texture.dispose(), [texture]);
  return texture;
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
  const land = useRef<Group>(null);
  const [hands, setHands] = useState(false);
  const anchor = useRef<Object3D | null>(null);
  // (One set of readouts for each place: where you are, there.)
  const readouts = [useReadoutTexture(0), useReadoutTexture(1), useReadoutTexture(2), useReadoutTexture(3)];
  const parts = useMemo(() => {
    const road = roadGeometry();
    return {
      panelGeometry: new PlaneGeometry(PANEL.w, PANEL.h),
      landGeometry: landGeometry(),
      markerGeometry: new PlaneGeometry(2, 2),
      road,
      panel: panelMaterial(PANEL.w / PANEL.h),
      terrain: terrainMaterial(),
      roadLine: roadMaterial(),
      // (Places passed: the way back's at the first; here; and ahead.)
      passed: PLACES.slice(0, 3).map(() => markerMaterial(MARKER.passed, [0.0085, 0.0085])),
      here: markerMaterial(MARKER.here, [0.017, 0.017]),
      ahead: markerMaterial(MARKER.ahead, [0.031, 0.0135]),
    };
  }, []);
  const passed = useRef<(Mesh | null)[]>([]);
  const hereMark = useRef<Mesh>(null);
  const aheadMark = useRef<Mesh>(null);

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
    // Arrived in a city, its map; otherwise the glance at the start, in the green city.
    const arrived = ride.transition.arrived;
    const m = arrived ? ride.transition.map : ride.preview;
    const here = arrived ? ride.zone : 0;
    const next = PLACES[here + 1];
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
    const t = state.clock.elapsedTime;
    // (Lowered, they turn down about a point below the chest, out of view: art/build-hands.py's pivot.)
    if (holder.current) {
      holder.current.rotation.x = -0.78 * (1 - raise);
      holder.current.position.set(0, -0.6 + 0.004 * Math.sin(t * 1.3), 0);
    }
    holoShared.uTime.value = t;
    holoShared.uOpen.value = open;

    // Its phosphor, here; the place's it's pointed at, for the way on.
    const accent = PLACES[here].accent;
    parts.panel.uniforms.uMap.value = readouts[here];
    parts.panel.uniforms.uAccent.value.set(accent);
    parts.terrain.uniforms.uAccent.value.set(accent);
    parts.roadLine.uniforms.uAccent.value.set(accent);
    parts.roadLine.uniforms.uHere.value = parts.road.at[here];
    parts.roadLine.uniforms.uNext.value = next ? parts.road.at[here + 1] : parts.road.at[here];
    parts.here.uniforms.uAccent.value.set(accent);
    parts.ahead.uniforms.uAccent.value.set(next?.accent ?? accent);
    // (The way on can be taken once this city's way out is known.)
    const onward = arrived && !!next && ZONES[here + 1] !== undefined && !!course.legs[here].end;
    const backHover = ride.mapBack.hover ? 1 : 0;
    const onHover = ride.mapOn.hover ? 1 : 0;
    parts.ahead.uniforms.uHover.value += (onHover - parts.ahead.uniforms.uHover.value) * 0.2;
    parts.panel.uniforms.uHover.value += (Math.max(backHover, onHover) - parts.panel.uniforms.uHover.value) * 0.2;
    for (const [i, material] of parts.passed.entries()) {
      material.uniforms.uAccent.value.set(PLACES[i].accent);
      const hover = i === 0 ? backHover : 0;
      material.uniforms.uHover.value += (hover - material.uniforms.uHover.value) * 0.2;
    }

    const p = panel.current;
    const g = land.current;
    if (!p || !g) return;
    p.visible = open > 0.001;
    // Over the projector's emitter, tilted back toward the eye: a white line that opens out, like a tube coming on.
    const a = anchor.current;
    if (a) {
      a.updateWorldMatrix(true, false);
      a.getWorldPosition(p.position);
      r.worldToLocal(p.position);
      p.position.y += PANEL.h / 2 + 0.012;
    } else p.position.set(0, -0.05, -0.62);
    p.rotation.set(-0.08, 0, 0);
    p.scale.set(Math.max(0.02, smoothstep(0, 0.3, open)), Math.max(0.012, smoothstep(0.22, 0.75, open)), 1);

    // The land on it, a little toward the eye, turning slowly and following the pointer; it twitches with the tears.
    const land01 = smoothstep(0.55, 1, open);
    g.visible = land01 > 0.001;
    g.position.copy(p.position);
    g.position.y -= 0.012;
    g.position.z += 0.05;
    g.position.x -= 0.02;
    const slot = Math.floor(t * 7);
    const glitch = Math.sin(slot * 91.7) * 43758.5453;
    if (glitch - Math.floor(glitch) > 0.9) g.position.x += ((glitch * 7.3) % 1) * 0.006;
    g.rotation.set(LAND.tilt, Math.sin(t * 0.3) * 0.2 + state.pointer.x * 0.16, 0);
    g.scale.setScalar(0.6 + 0.4 * land01);

    // Its markers, on the land.
    for (const [i, mesh] of passed.current.entries()) if (mesh) mesh.visible = i < here;
    if (hereMark.current) hereMark.current.position.copy(onLand(PLACES[here].x, PLACES[here].y, 0.012));
    const am = aheadMark.current;
    if (am) {
      am.visible = !!next;
      if (next) am.position.copy(onLand(next.x, next.y, 0.03));
    }

    // Where the way back and the way on are on screen, for the buttons over them.
    const onScreen = (target: typeof ride.mapBack, shown: boolean, mark: Object3D | null | undefined, hw: number, hh: number) => {
      target.shown = shown && !!mark;
      if (!target.shown || !mark) return;
      mark.updateWorldMatrix(true, false);
      mark.getWorldPosition(view).applyMatrix4(state.camera.matrixWorldInverse);
      let x0 = Number.POSITIVE_INFINITY;
      let y0 = Number.POSITIVE_INFINITY;
      let x1 = Number.NEGATIVE_INFINITY;
      let y1 = Number.NEGATIVE_INFINITY;
      for (const [sx, sy] of [
        [-1, -1],
        [1, -1],
        [-1, 1],
        [1, 1],
      ]) {
        corner.set(view.x + sx * hw, view.y + sy * hh, view.z).applyMatrix4(state.camera.projectionMatrix);
        const x = (corner.x * 0.5 + 0.5) * state.size.width;
        const y = (-corner.y * 0.5 + 0.5) * state.size.height;
        x0 = Math.min(x0, x);
        x1 = Math.max(x1, x);
        y0 = Math.min(y0, y);
        y1 = Math.max(y1, y);
      }
      Object.assign(target, { x: x0, y: y0, w: x1 - x0, h: y1 - y0 });
    };
    onScreen(ride.mapBack, arrived && open > 0.95, passed.current[0], 0.02, 0.02);
    onScreen(ride.mapOn, onward && open > 0.95, am, 0.035, 0.019);
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
      <mesh ref={panel} geometry={parts.panelGeometry} material={parts.panel} renderOrder={21} frustumCulled={false} />
      <group ref={land} visible={false}>
        <mesh geometry={parts.landGeometry} material={parts.terrain} renderOrder={22} frustumCulled={false} />
        <mesh geometry={parts.road.geometry} material={parts.roadLine} renderOrder={23} frustumCulled={false} />
        {parts.passed.map((material, i) => (
          <mesh
            key={PLACES[i].accent}
            ref={(m) => {
              passed.current[i] = m;
            }}
            geometry={parts.markerGeometry}
            material={material}
            position={onLand(PLACES[i].x, PLACES[i].y, 0.01)}
            renderOrder={24}
            frustumCulled={false}
          />
        ))}
        <mesh ref={hereMark} geometry={parts.markerGeometry} material={parts.here} renderOrder={25} frustumCulled={false} />
        <mesh ref={aheadMark} geometry={parts.markerGeometry} material={parts.ahead} renderOrder={24} frustumCulled={false} />
      </group>
    </group>
  );
}
