'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo } from 'react';
import {
  AdditiveBlending,
  Box3,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  LineBasicMaterial,
  LineSegments,
  type MeshStandardMaterial,
  Sprite,
  SpriteMaterial,
  Vector3,
} from 'three';
import { isLightDevice, journey, smoothstep } from '@/lib/journey';
import { ACCEL, anchors, BRAKE, CRUISE, ride, SETTLED_FRAME } from '@/lib/ride';

// The ride button's entrance: once the camera has settled on the landing, streaks of light fly in from all round the
// bike and converge between the handlebars, where the button lights (components/three/bike.tsx gives it its glow from
// ride.appear and ride.near). Streak timing, in seconds after settling:
const FLY = 1.3; // the last streaks arrive by then
const LIT = [1.0, 1.7] as const; // the button comes up as they land
const STREAKS = 48;
const SEGMENTS = 14; // per streak's trail
const TRAIL = 0.32; // trail length, as a share of the flight
const MOUNT_SECONDS = 2.2;

const target = new Vector3();
const edge = new Vector3();
const p = new Vector3();
const ndc = new Vector3();
const box = new Box3();
const corner = new Vector3();

type Streak = { from: Vector3; bend: Vector3; delay: number; duration: number };

function bezier(out: Vector3, a: Vector3, b: Vector3, c: Vector3, t: number) {
  const u = 1 - t;
  return out
    .copy(a)
    .multiplyScalar(u * u)
    .addScaledVector(b, 2 * u * t)
    .addScaledVector(c, t * t);
}

/** Times the entrance, tracks the button on screen and the pointer's distance, and eases the camera's mount. */
export function RideControl({ buttonMaterials }: { buttonMaterials: { current: MeshStandardMaterial[] } }) {
  const coarse = useMemo(() => typeof window !== 'undefined' && window.matchMedia('(pointer: coarse)').matches, []);

  useFrame((state, delta) => {
    if (process.env.NODE_ENV === 'development') (window as unknown as { __ride?: unknown }).__ride = { ride, anchors };
    const dt = Math.min(delta, 1 / 20);
    const settled = journey.frame >= SETTLED_FRAME;
    // (Running back quickly when the visitor scrolls away, so it can play again.)
    ride.since = settled ? Math.min(ride.since + dt, 10) : Math.max(0, ride.since - dt * 3);
    ride.appear = smoothstep(LIT[0], LIT[1], ride.since);
    if (!settled && ride.mounted) ride.mounted = false;

    // (The camera has moved this frame, but its matrices only update when it renders.)
    state.camera.updateMatrixWorld();
    // The button on screen: its centre and a radius from a point on its rim.
    const button = anchors.button;
    if (button) {
      button.getWorldPosition(target);
      edge.set(0.12, 0, 0);
      button.localToWorld(edge);
      ndc.copy(target).project(state.camera);
      const x = (ndc.x * 0.5 + 0.5) * state.size.width;
      const y = (-ndc.y * 0.5 + 0.5) * state.size.height;
      const rim = edge.project(state.camera);
      const r = Math.hypot((rim.x * 0.5 + 0.5) * state.size.width - x, (-rim.y * 0.5 + 0.5) * state.size.height - y);
      ride.screen.x = x;
      ride.screen.y = y;
      ride.screen.r = Math.max(r, 10);
      // (From the landing once it's lit; on the bike, once seated, it's the throttle.)
      ride.screen.shown = ndc.z < 1 && ride.appear > 0.6 && ((!ride.mounted && ride.mount < 0.05) || (ride.mounted && ride.mount > 0.95));
    }
    // The whole bike's box on screen: anywhere on it gets on.
    if (anchors.bike) {
      box.setFromObject(anchors.bike);
      const b = ride.bike;
      b.x0 = b.y0 = Number.POSITIVE_INFINITY;
      b.x1 = b.y1 = Number.NEGATIVE_INFINITY;
      for (let i = 0; i < 8; i++) {
        corner.set(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).project(state.camera);
        const x = (corner.x * 0.5 + 0.5) * state.size.width;
        const y = (-corner.y * 0.5 + 0.5) * state.size.height;
        b.x0 = Math.min(b.x0, x);
        b.x1 = Math.max(b.x1, x);
        b.y0 = Math.min(b.y0, y);
        b.y1 = Math.max(b.y1, y);
      }
    }

    // Brighter the nearer the pointer: full on the button, falling off over a few of its widths. Without a pointer
    // (touch) it breathes instead.
    let near = 0;
    if (ride.focused) near = 1;
    else if (ride.pointer && !coarse) {
      const d = Math.hypot(ride.pointer.x - ride.screen.x, ride.pointer.y - ride.screen.y);
      near = 1 - smoothstep(ride.screen.r * 1.2, ride.screen.r * 7 + 140, d);
      // (Anywhere over the bike, since all of it is clickable, it's well lit.)
      const { x0, y0, x1, y1 } = ride.bike;
      if (ride.pointer.x > x0 && ride.pointer.x < x1 && ride.pointer.y > y0 && ride.pointer.y < y1) near = Math.max(near, 0.6);
    } else near = 0.25 + 0.25 * Math.sin(state.clock.elapsedTime * 1.6);
    // (On the bike it stays lit and breathes: it's the control for riding on.)
    if (ride.mount > 0.5) near = 0.3 + 0.2 * Math.sin(state.clock.elapsedTime * 1.6);
    // (Eased, so it swells rather than snaps.)
    ride.near += (near - ride.near) * Math.min(1, dt * 8);
    // (Pixel mode draws the scene at a quarter of the resolution: the small button needs more light to survive it.)
    const boost = state.gl.getPixelRatio() < 1 ? 2 : 1;
    for (const m of buttonMaterials.current) {
      const glyph = m.name === 'BikeButtonGlyph';
      m.emissiveIntensity = ride.appear * (glyph ? 1.8 + 5 * ride.near : 0.2 + 1.4 * ride.near) * boost;
    }

    // Getting on: an eased glide there and back.
    const goal = ride.mounted ? 1 : 0;
    ride.mount = goal > ride.mount ? Math.min(goal, ride.mount + dt / MOUNT_SECONDS) : Math.max(goal, ride.mount - dt / MOUNT_SECONDS);

    // Riding on (this runs before the bike moves and the camera follows: components/three/bike.tsx): up to cruising speed (plus any boost from scrolling) once it's told to go, braking to a stop when not.
    const drive = ride.drive;
    if (ride.mounted) {
      drive.rewindFrom = -1;
      const want = ride.mount > 0.95 && drive.cruise ? CRUISE + drive.boost : 0;
      drive.speed = want > drive.speed ? Math.min(want, drive.speed + ACCEL * dt) : Math.max(want, drive.speed - BRAKE * dt);
      drive.s += drive.speed * dt;
    } else {
      // Getting off rewinds the ride, the bike sliding back to its spot as the camera glides back to the landing.
      drive.cruise = false;
      drive.speed = 0;
      if (drive.s > 0) {
        if (drive.rewindFrom < 0) drive.rewindFrom = drive.s;
        drive.s = drive.rewindFrom * smoothstep(0, 1, ride.mount);
      } else drive.rewindFrom = -1;
    }
    drive.boost = Math.max(0, drive.boost - dt * 5);
    drive.away = smoothstep(20, 260, drive.s);
  });

  return null;
}

/** A soft halo of light round the button, brighter as the pointer nears: it's what still reads once pixelated. */
export function RideHalo() {
  const halo = useMemo(() => {
    const size = 128;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const ctx = canvas.getContext('2d') as CanvasRenderingContext2D;
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.18, 'rgba(255,255,255,0.55)');
    g.addColorStop(0.5, 'rgba(255,255,255,0.12)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    const material = new SpriteMaterial({
      map: new CanvasTexture(canvas),
      color: new Color(0.75, 1.0, 0.6).multiplyScalar(1.8),
      transparent: true,
      blending: AdditiveBlending,
      depthWrite: false,
      toneMapped: false,
      opacity: 0,
    });
    const sprite = new Sprite(material);
    sprite.renderOrder = 7;
    return sprite;
  }, []);

  useFrame((state) => {
    const button = anchors.button;
    const on = ride.appear * (1 - ride.mount);
    halo.visible = !!button && on > 0.001;
    if (!button || !halo.visible) return;
    button.getWorldPosition(halo.position);
    // Bigger and brighter when pixelated, so it still reads in the coarse cells.
    const pixel = state.gl.getPixelRatio() < 1;
    halo.scale.setScalar((0.24 + 0.12 * ride.near) * (pixel ? 1.6 : 1));
    halo.material.opacity = on * (0.16 + 0.55 * ride.near) * (pixel ? 1.3 : 1);
  });

  return <primitive object={halo} />;
}

/** The light streaks converging between the handlebars. */
export function RideStreaks() {
  const { lines, streaks } = useMemo(() => {
    const count = isLightDevice() ? STREAKS / 2 : STREAKS;
    const streaks: Streak[] = [];
    for (let i = 0; i < count; i++) {
      // From a shell round the bike, mostly above and to the sides (in view from the landing), each on a curved path.
      const a = Math.random() * Math.PI * 2;
      const up = 0.15 + Math.random() * 0.85;
      const r = 2.5 + Math.random() * 4.5;
      const from = new Vector3(Math.cos(a) * r * Math.sqrt(1 - up * up), up * r, Math.sin(a) * r * Math.sqrt(1 - up * up));
      const bend = new Vector3((Math.random() - 0.5) * 3, (Math.random() - 0.2) * 2, (Math.random() - 0.5) * 3);
      streaks.push({ from, bend, delay: Math.random() * 0.45, duration: 0.55 + Math.random() * (FLY - 0.6) });
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new BufferAttribute(new Float32Array(count * SEGMENTS * 2 * 3), 3));
    geometry.setAttribute('color', new BufferAttribute(new Float32Array(count * SEGMENTS * 2 * 3), 3));
    const material = new LineBasicMaterial({ vertexColors: true, transparent: true, blending: AdditiveBlending, depthWrite: false, toneMapped: false });
    const lines = new LineSegments(geometry, material);
    lines.frustumCulled = false;
    lines.renderOrder = 6;
    return { lines, streaks };
  }, []);
  const tint = useMemo(() => new Color(0.75, 1.0, 0.6), []);

  useFrame(() => {
    const button = anchors.button;
    const t = ride.since;
    lines.visible = !!button && t > 0 && t < FLY + 0.4 && ride.mount < 0.5;
    if (!lines.visible || !button) return;
    button.getWorldPosition(target);
    const positions = lines.geometry.attributes.position as BufferAttribute;
    const colours = lines.geometry.attributes.color as BufferAttribute;
    const start = new Vector3();
    const mid = new Vector3();
    let v = 0;
    for (const s of streaks) {
      start.copy(s.from).add(target);
      mid.copy(start).lerp(target, 0.5).add(s.bend);
      // The head races in, accelerating; the trail follows a fixed share behind it.
      const head = Math.min(1, Math.max(0, (t - s.delay) / s.duration)) ** 1.6;
      const tail = Math.max(0, head - TRAIL);
      // Fades once it's landed.
      const life = head >= 1 ? Math.max(0, 1 - (t - s.delay - s.duration) * 4) : head > 0 ? 1 : 0;
      for (let k = 0; k < SEGMENTS; k++) {
        const u0 = tail + ((head - tail) * k) / SEGMENTS;
        const u1 = tail + ((head - tail) * (k + 1)) / SEGMENTS;
        bezier(p, start, mid, target, u0);
        positions.setXYZ(v, p.x, p.y, p.z);
        // Brightest at the head, past white so the bloom catches it.
        const b0 = (k / SEGMENTS) ** 2 * 6 * life;
        colours.setXYZ(v++, tint.r * b0, tint.g * b0, tint.b * b0);
        bezier(p, start, mid, target, u1);
        positions.setXYZ(v, p.x, p.y, p.z);
        const b1 = ((k + 1) / SEGMENTS) ** 2 * 6 * life;
        colours.setXYZ(v++, tint.r * b1, tint.g * b1, tint.b * b1);
      }
    }
    positions.needsUpdate = true;
    colours.needsUpdate = true;
  });

  return <primitive object={lines} />;
}
