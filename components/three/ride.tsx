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
import { course, courseCurve, groundAt, inLength, legIndexAt, placeAfter, resetCourse, ZONES } from '@/lib/course';
import { isLightDevice, journey, smoothstep } from '@/lib/journey';
import { updateLook } from '@/lib/look';
import { updateMusic } from '@/lib/music';
import { heartPeriod, rhythm, updateRhythm } from '@/lib/rhythm';
import {
  ACCEL,
  anchors,
  BRAKE,
  bikeReady,
  boostHere,
  CHROME_SECONDS,
  cutGhost,
  featureHere,
  GHOST_SHED,
  HEART,
  JUMP,
  LAUNCH_SECONDS,
  MORPH_AFTER,
  muckUnder,
  resetGhost,
  ride,
  road,
  SETTLED_FRAME,
  TRANSITION_LEAD,
  transitionLead,
  transitionTail,
  updateGhost,
  WASH,
  WASH_FROM,
} from '@/lib/ride';
import { trace, updateTrace } from '@/lib/trace';
import { AT } from './bike';
import { pillGlyphs } from './pill-glyph';

// The ride button's entrance: once the camera has settled on the landing, streaks of light fly in from all round the
// bike and converge between the handlebars, where the button lights (components/three/bike.tsx gives it its glow from
// ride.appear and ride.near). Streak timing, in seconds after settling:
const FLY = 1.3; // the last streaks arrive by then
const LIT = [1.0, 1.7] as const; // the button comes up as they land
const STREAKS = 48;
const SEGMENTS = 14; // per streak's trail
const TRAIL = 0.32; // trail length, as a share of the flight
const MOUNT_SECONDS = 2.2;
// Through the ooze: the speed it bogs down to (m/s) and how hard it drags (m/s²).
const MUCK_SPEED = 8;
const CLEAR_SECONDS = 4;
// The map: how long after the arrival shot settles, and how long the camera's return, the hands and the opening take.
const MAP_AFTER = 3.5;
// The glance at the map getting on: up (hands, opening), held, put away (s).
const PREVIEW = { up: 2.2, hold: 1.6, down: 1.0 };
const MAP_SECONDS = 4.5;
const MUCK_DRAG = 26;

const target = new Vector3();
const edge = new Vector3();
const p = new Vector3();
const ndc = new Vector3();
const box = new Box3();
const corner = new Vector3();

// How much harder it brakes shedding a boost that's been cut off.
const SHED = 5;
let featureWas = '';
function cutBoost() {
  const d = ride.drive;
  const boosted = d.surge > 0.01 || d.pump > 0.01 || d.launch > 0.01;
  Object.assign(d, { boosting: false, surge: 0, pump: 0, launch: 0, pull: 0, release: 0, boost: 0 });
  if (boosted) d.shedding = true;
  cutGhost();
}

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
    if (process.env.NODE_ENV === 'development')
      (window as unknown as { __ride?: unknown; __trace?: unknown }).__ride = { ride, anchors, rhythm, scene: state.scene };
    if (process.env.NODE_ENV === 'development') (window as unknown as { __trace?: unknown }).__trace = trace;
    const dt = Math.min(delta, 1 / 20);
    const settled = journey.frame >= SETTLED_FRAME;
    // Counting up once settled on the landing; before the button's been lit it runs back when the visitor scrolls away,
    // so the streaks play again on return. Once lit, it stays lit.
    if (settled || ride.activated) ride.since = Math.min(ride.since + dt, 10);
    else ride.since = Math.max(0, ride.since - dt * 3);
    ride.appear = smoothstep(LIT[0], LIT[1], ride.since);
    if (ride.appear >= 1) ride.activated = true;
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
      ride.screen.shown = ndc.z < 1 && ride.wash < 0 && ride.appear > 0.6 && ((!ride.mounted && ride.mount < 0.05) || (ride.mounted && ride.mount > 0.95));
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
    const drive = ride.drive;
    // The button: its play or pause symbol lit bright on the pill (dim, so the symbol reads through the pixels).
    const symbol = ride.mounted && drive.cruise ? pillGlyphs().pause : pillGlyphs().play;
    for (const m of buttonMaterials.current) {
      const glyph = m.name.endsWith('ButtonGlyph');
      m.emissiveIntensity = ride.appear * (glyph ? 2.4 + 3 * ride.near : 0.1 + 0.3 * ride.near) * boost;
      if (glyph && m.emissiveMap !== symbol) {
        m.emissiveMap = symbol;
        m.alphaMap = symbol;
      }
    }

    // Getting on: an eased glide there and back.
    const goal = ride.mounted ? 1 : 0;
    // (Held on the bike while a wash comes in: it puts everything back at once, under cover.)
    const washing = ride.wash >= 0 && ride.wash < WASH.in;
    if (!washing) ride.mount = goal > ride.mount ? Math.min(goal, ride.mount + dt / MOUNT_SECONDS) : Math.max(goal, ride.mount - dt / MOUNT_SECONDS);

    // Riding on (this runs before the bike moves and the camera follows: components/three/bike.tsx): up to cruising
    // speed (plus any boost from scrolling) once it's told to go, braking to a stop when not. Each zone has its own
    // cruising speed and its own feature on the throttle (lib/course.ts ZONES), pushing it on far faster.
    const tr = ride.transition;
    const feature = featureHere();
    updateRhythm(dt, ride.mounted && feature === 'heartbeat' && drive.cruise && !tr.arrived);
    // (The hive's circles and the chrome city's trace can each slow the ride right down, to show what's wanted.)
    const step = dt * Math.min(rhythm.slow, trace.slow);
    updateGhost(dt);
    updateTrace(dt, ride.mounted && ride.mount > 0.95 && feature === 'surge' && drive.cruise && !tr.arrived);
    const ghost = feature === 'ghost' ? ride.ghost.kick : 0;
    // A boost belongs to the zone it's used in: into the next, it's cut off, the bike shedding the speed quickly.
    if (feature !== featureWas) {
      featureWas = feature;
      cutBoost();
    }
    if (ride.mounted) {
      drive.rewindFrom = -1;
      // The chrome city's surge: as far as the trace has built, easing in and out (lib/trace.ts).
      const surging = drive.cruise && feature === 'surge' ? trace.level : 0;
      drive.surge += (surging - drive.surge) * Math.min(1, dt * (surging > drive.surge ? 2.2 : 2.4));
      // The desert's slingshot: the button drawn back along its track (it snaps home fast when let go); let go, the
      // bike's flung on, the kick running down over a few seconds.
      if (feature !== 'slingshot') drive.pull = 0;
      drive.draw += (drive.pull - drive.draw) * Math.min(1, dt * (drive.pull > drive.draw ? 16 : 30));
      if (drive.release > 0) {
        drive.launch = Math.max(drive.launch, drive.release);
        drive.speed += 40 * drive.release;
        drive.cruise = true;
        drive.release = 0;
      }
      drive.launch = Math.max(0, drive.launch - dt / LAUNCH_SECONDS);
      drive.fire += (Math.min(1, drive.launch * 1.5) - drive.fire) * Math.min(1, dt * (drive.launch * 1.5 > drive.fire ? 14 : 3));
      // The hive's heartbeat: the heart beats on, quicker as the run of circles goes on (lib/rhythm.ts) and with the boost it
      // ends in, which ebbs away.
      drive.phase = (drive.phase + step / heartPeriod()) % 1;
      drive.beat =
        Math.exp(-((drive.phase / 0.06) ** 2)) + 0.6 * Math.exp(-(((drive.phase - 0.28) / 0.07) ** 2)) + Math.exp(-(((drive.phase - 1) / 0.06) ** 2));
      drive.pump = Math.max(0, drive.pump - step * (feature === 'heartbeat' ? HEART.ebb : 1));
      const kick = feature === 'surge' ? drive.surge : feature === 'heartbeat' ? drive.pump : feature === 'slingshot' ? drive.launch : ghost;
      // (Cruising speed changes with the zone, over the change between them.)
      const cruise = ZONES[Math.max(0, ride.zone - 1)].cruise + (ZONES[ride.zone].cruise - ZONES[Math.max(0, ride.zone - 1)].cruise) * tr.t;
      let want = ride.mount > 0.95 && drive.cruise ? cruise * (1 + boostHere() * kick) + drive.boost : 0;
      // (Drawn back, it holds back a little, like a bow.)
      want *= 1 - 0.35 * drive.draw;
      // In a city, the ride slows to pull up at the end of its road, the bike's spot there (until the visitor rides on).
      const leg = course.legs[ride.zone];
      const stop = tr.placed ? leg.at + inLength(leg) : Number.POSITIVE_INFINITY;
      if (tr.placed) {
        const left = stop - drive.s;
        // (Gently over the last stretch; hard on the brakes before it, so a surge or a launch runs on until near the end.)
        // (The ghost's far quicker, and brakes far harder: its curve's its own, or it would start braking kilometres out.)
        const brakes = feature === 'ghost' ? BRAKE * GHOST_SHED : BRAKE;
        const stopping = Math.max(Math.sqrt(2 * 3.2 * Math.max(0, left - 0.3)), Math.sqrt(2 * brakes * Math.max(0, left - 150)));
        if (feature === 'ghost' && want > stopping && drive.speed > stopping + 20) {
          cutGhost();
          drive.shedding = true;
        }
        want = Math.min(want, stopping);
        // Nearing the next zone's road, however it's boosted, it's down to that zone's cruising speed by the join.
        const cap = ZONES[ride.zone].cruise + Math.sqrt(2 * BRAKE * SHED * Math.max(0, tr.at - 40 - drive.s));
        if (drive.s < tr.at && want > cap) {
          want = cap;
          if (drive.speed > cap) drive.shedding = true;
        }
        // Through a slick of ooze it bogs down, as in muck.
        const k = legIndexAt(drive.s);
        if (k > 0 && muckUnder(drive.s - course.legs[k].at, k) > 0.01) {
          want = Math.min(want, MUCK_SPEED);
          if (drive.speed > MUCK_SPEED) drive.speed = Math.max(MUCK_SPEED, drive.speed - MUCK_DRAG * dt);
        }
        // (And takes the bends at a speed it can lean into, about 25° over: looking a little ahead for the next.)
        if (drive.s > course.legs[1].at - 60) {
          let curve = 0;
          for (let ahead = 0; ahead <= 60 + drive.speed; ahead += 10) curve = Math.max(curve, Math.abs(courseCurve(drive.s + ahead)));
          // (With the zone's feature going, it leans harder and takes them faster: the more its boost, the faster.)
          // (Not as data: it doesn't lean, it goes through.)
          if (curve > 1e-4 && ghost <= 0) want = Math.min(want, Math.sqrt((9.8 * Math.tan(0.44 + 0.4 * kick)) / curve) * (1 + 0.43 * boostHere() * kick));
        }
        // (Only once its road's known: a zone still loading holds the ride at the end of the last one's way out.)
        if (left < 0.6 && drive.speed < 0.4 && !tr.arrived && leg.in) {
          tr.arrived = true;
          drive.cruise = false;
          cutBoost();
        }
      }
      drive.speed =
        want > drive.speed
          ? Math.min(want, drive.speed + ACCEL * (1 + 8 * drive.launch + 8 * drive.pump + 8 * drive.surge + 90 * ghost) * step)
          : Math.max(want, drive.speed - BRAKE * (drive.shedding ? (feature === 'ghost' ? GHOST_SHED : SHED) : 1) * step);
      if (drive.speed <= want + 0.5) drive.shedding = false;
      drive.s = Math.min(drive.s + drive.speed * step, stop);
      if (drive.speed > 0.5) drive.time += step;
      // Over the dunes: it follows the ground while the ground's rising or falling away slower than it would drop, and
      // past a crest it flies; it lands with a thump.
      if (step > 0) {
        // (Under its front wheel as well as its middle: it rides up onto a dune nose first, not buried to the tank.)
        const ground = Math.max(groundAt(drive.s), groundAt(drive.s + 3));
        const falling = drive.y + drive.vy * step - (JUMP.gravity * step * step) / 2;
        if (falling <= ground) {
          if (drive.air) drive.land = Math.min(1, Math.max(drive.land, -drive.vy / 14));
          drive.air = false;
          drive.vy = Math.max(-JUMP.rise, Math.min(JUMP.rise, (ground - drive.y) / step));
          drive.y = ground;
        } else {
          drive.air = true;
          drive.y = falling;
          drive.vy -= JUMP.gravity * step;
        }
      }
      drive.land = Math.max(0, drive.land - dt * 4);
      drive.pitch += (Math.atan2(drive.vy, Math.max(drive.speed, 10)) - drive.pitch) * Math.min(1, dt * 7);
    } else {
      drive.cruise = false;
      drive.speed = 0;
      drive.boosting = false;
      drive.surge = 0;
      resetGhost();
      Object.assign(drive, { pull: 0, draw: 0, release: 0, launch: 0, fire: 0, pump: 0, y: 0, vy: 0, air: false, land: 0, pitch: 0 });
      if (ride.wash < 0 && drive.s > WASH_FROM) ride.wash = 0;
      if (ride.wash >= 0) {
        // Getting off after a ride: the liquid wash, everything put back once it covers the screen.
        const before = ride.wash;
        ride.wash += dt;
        if (before < WASH.in && ride.wash >= WASH.in) {
          drive.s = 0;
          drive.rewindFrom = -1;
          ride.mount = 0;
          // (Back at the landing, the bike's its black self again.)
          Object.assign(ride.morph, { from: 0, to: 0, at: 0 });
          drive.time = 0;
          // (And the cities are gone again: the next ride makes its way there afresh.)
          resetCourse();
          ride.zone = 1;
          Object.assign(tr, { placed: false, at: 0, t: 0, arrived: false, arrive: 0, clear: 0, held: 0, map: 0 });
        }
        if (ride.wash > WASH.in + WASH.hold + WASH.out) ride.wash = -1;
      } else if (drive.s > 0) {
        // Only just rolled off: the bike slides back to its spot as the camera glides back to the landing.
        if (drive.rewindFrom < 0) drive.rewindFrom = drive.s;
        drive.s = drive.rewindFrom * smoothstep(0, 1, ride.mount);
      } else {
        drive.rewindFrom = -1;
        drive.time = 0;
      }
    }
    drive.boost = Math.max(0, drive.boost - dt * 5);
    // The change to the chrome city: once it's loaded and the ride's been going a while, it's placed a stretch down
    // the street ahead, the sky turns from green night to its sunset as the bike nears it, and the bike's morph runs.
    const first = course.legs[1];
    if (ride.zone === 1 && !first.placed && first.ready && ride.mounted && drive.time > MORPH_AFTER) {
      first.at = drive.s + TRANSITION_LEAD;
      first.origin.set(AT[0], AT[1], AT[2]).addScaledVector(road.ahead, first.at);
      first.yaw = road.yaw;
      first.placed = true;
      tr.placed = true;
      tr.at = first.at;
    }
    // Riding on from a city's plaza (picked on the map): the next zone is placed where its way out ends, and the ride
    // heads there, the sky changing over the way out.
    if (ride.request.on) {
      ride.request.on = false;
      const next = ride.zone + 1;
      if (tr.arrived && next < ZONES.length && placeAfter(next)) {
        ride.zone = next;
        Object.assign(tr, { placed: true, at: course.legs[next].at, t: 0, arrived: false, arrive: 0, held: 0, map: 0 });
        drive.cruise = true;
      }
    }
    // (Every change alike: over the road either side of where the next city's takes over.)
    tr.t = tr.placed ? smoothstep(tr.at - transitionLead(ride.zone), tr.at + transitionTail(ride.zone), drive.s) : 0;
    // The towers by the water sink away and the train's beam rises in their place, over a few seconds.
    tr.clear = tr.placed ? Math.min(1, tr.clear + dt / CLEAR_SECONDS) : 0;
    tr.arrive = tr.arrived && ride.mounted ? Math.min(1, tr.arrive + dt / 3.2) : Math.max(0, tr.arrive - dt / 1.2);
    // Getting on, a glance at the map: hands up, it opens, held a moment, put away; cut short by setting off.
    if (ride.mounted && ride.mount > 0.98 && ride.previewTime < 0 && !tr.placed) ride.previewTime = 0;
    if (!ride.mounted) ride.previewTime = -1;
    if (ride.previewTime >= 0) {
      ride.previewTime += dt;
      const t = ride.previewTime;
      const up = Math.min(1, t / PREVIEW.up);
      const down = Math.min(1, Math.max(0, (t - PREVIEW.up - PREVIEW.hold) / PREVIEW.down));
      ride.preview = drive.cruise ? Math.max(0, ride.preview - dt / PREVIEW.down) : up * (1 - down);
      if (ride.preview <= 0 && t > PREVIEW.up) ride.previewTime = 99;
    } else ride.preview = 0;
    // A few seconds on the arrival shot, then the map: back on the bike, the hands come up with it.
    tr.held = tr.arrive >= 1 ? tr.held + dt : 0;
    tr.map = tr.arrived && ride.mounted ? Math.min(1, Math.max(tr.map, (tr.held - MAP_AFTER) / MAP_SECONDS)) : Math.max(0, tr.map - dt / 0.8);
    // The bike's morph into the zone's own: timed for its seam to be halfway along as the bike crosses onto the next
    // city's road, the middle of the change. (The chrome one can start before its bike's loaded: the black one turns to
    // chrome itself until it is; the others wait.)
    const m = ride.morph;
    const crossing = drive.s + (drive.speed * CHROME_SECONDS) / 2 >= tr.at;
    if (tr.placed && ride.mounted && crossing && m.from === m.to && m.to !== ride.zone && (ride.zone === 1 || bikeReady[ride.zone])) {
      Object.assign(m, { from: m.to, to: ride.zone, at: 0 });
    }
    if (m.from !== m.to) {
      m.at = Math.min(1, m.at + dt / CHROME_SECONDS);
      if (m.at >= 1) m.from = m.to;
    }
    // The light now, from the zones' looks.
    updateLook();
    updateMusic(dt);
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
