'use client';

import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  AddEquation,
  BufferAttribute,
  type BufferGeometry,
  Color,
  CustomBlending,
  DoubleSide,
  type Group,
  InstancedBufferAttribute,
  InstancedBufferGeometry,
  LinearFilter,
  type Mesh,
  NoColorSpace,
  type Object3D,
  OneFactor,
  OneMinusSrcAlphaFactor,
  ShaderMaterial,
  type Texture,
  TextureLoader,
  Vector2,
  Vector3,
  ZeroFactor,
} from 'three';
import { course, type Path } from '@/lib/course';
import { doorOpen, doorState } from '@/lib/doors';
import { devFlag, isLightDevice, NO_MIRROR_LAYER, smoothstep } from '@/lib/journey';
import { ride } from '@/lib/ride';
import { loadSectionAudio, playSectionSound, sectionImpact, updateSectionAudio } from '@/lib/section-audio';
import { pathValue, placeSectionFx, type SectionFxPlaces, TUBE } from '@/lib/section-fx';
import { sections } from '@/lib/sections';
import { precompile } from './precompile';
import { makeWater } from './section-fx-water';

// What the stairwell's and flooded tunnel's models don't have: the water's surface (section-fx-water.ts), spray up both sides of the bike and
// the splash into the water; steam, sparks and drips in the stairwell; their sound (lib/section-audio.ts). All flipbooks (art/core/fx), a few cards
// each, one draw per book, everything worked out in the vertex shader from a handful of uniforms. Nothing's fetched or drawn away from them.

/** How far short of the stairwell it fetches what it needs. */
const LOAD_AHEAD = 300;

/** The book's cell for frame `f`, and the card's corner q. */
const CELL = /* glsl */ `
vec2 cell(float f, vec2 q, float flip) {
  float col = mod(f, 8.0);
  float row = floor(f / 8.0);
  float x = flip > 0.0 ? q.x : 1.0 - q.x;
  return vec2((col + x) / 8.0, 1.0 - (row + 1.0 - q.y) / 8.0);
}`;

const FRAGMENT = /* glsl */ `
uniform sampler2D uMap;
uniform vec3 uTint;
uniform float uCover;
uniform vec2 uCurve;
uniform float uClock;
varying vec2 vCell;
varying float vAlpha;
varying float vShade;
void main() {
  float a = smoothstep(uCurve.x, uCurve.y, texture2D(uMap, vCell).r) * vAlpha;
  #ifdef GRAIN
    // Spray is drops, not fog: each of the scene's pixels is a drop or it isn't, by the book's density, so a stack of cards stays grainy
    // white on dark instead of averaging to grey. (The speed blur draws them out into streaks.)
    float seed = dot(floor(gl_FragCoord.xy), vec2(12.9898, 78.233)) + vShade * 91.7 + uClock * 3.7;
    float h = fract(sin(seed) * 43758.5453);
    if (h > a) discard;
    float shade = 0.3 + 0.95 * fract(h * 57.31);
    gl_FragColor = vec4(uTint * vShade * shade, 1.0);
  #else
    gl_FragColor = vec4(uTint * vShade * a, a * uCover);
  #endif
  #include <colorspace_fragment>
}`;

// Spray goes with the bike: each card's thrown off the water ahead, rushes back along a line opening out from the bike's nose, past the
// eye and out of the frame's corners, running through the book as it goes, and then round again. Its place is in the uniforms.
const SPRAY_VERTEX = /* glsl */ `
attribute vec4 aPlace;  // ahead from, out from, size, side
attribute vec4 aRoute;  // ahead to, out to, height, the book's frame it starts on
attribute vec4 aPlay;   // phase, rate, shade, burst
uniform vec3 uAt;
uniform vec3 uAhead;
uniform float uClock;
uniform float uAmount;
uniform float uSplash;
uniform float uSplashSize;
uniform float uNarrow;
varying vec2 vCell;
varying float vAlpha;
varying float vShade;
${CELL}
void main() {
  bool burst = aPlay.w > 0.5;
  float t = burst ? clamp(uSplash * aPlay.y + aPlay.x, 0.0, 1.0) : fract(uClock * aPlay.y + aPlay.x);
  float amount = burst ? (uSplash < 0.0 ? 0.0 : uSplashSize) : uAmount;
  if (amount < 0.002 || (burst && t >= 0.999)) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    return;
  }
  vec3 out_ = vec3(-uAhead.z, 0.0, uAhead.x) * aPlace.w;
  vec3 base = uAt + uAhead * mix(aPlace.x, aRoute.x, t) + out_ * mix(aPlace.y, aRoute.y, t) * uNarrow * (0.72 + 0.28 * min(amount, 1.0));
  float size = aPlace.z * (0.55 + 0.75 * t) * (0.4 + 0.6 * min(amount, 1.4));
  vec3 right = vec3(viewMatrix[0][0], viewMatrix[1][0], viewMatrix[2][0]) * aPlace.w;
  vec3 world = base + right * (position.x - 0.1) * size * 1.3 + vec3(0.0, 1.0, 0.0) * (position.y - 0.08) * size * aRoute.z;
  vec4 mv = viewMatrix * vec4(world, 1.0);
  gl_Position = projectionMatrix * mv;
  // (Past its first blob of frames, which is the book's start, out towards its fine end.)
  float f = floor(mix(aRoute.w, min(aRoute.w + 45.0, 63.0), t));
  // (The card is mirrored by its right axis, for the other side: the book is read the same way.)
  vCell = cell(f, position.xy, 1.0);
  vAlpha = min(amount, 1.0) * 0.52 * smoothstep(0.0, 0.1, t) * smoothstep(1.0, burst ? 0.55 : 0.9, t) * smoothstep(0.25, 1.1, -mv.z);
  vShade = aPlay.z;
}`;

// Steam, sparks and drips stay where they are: cards standing along an axis (up, or a jet's way across the road), each a burst's, or looping.
const STATIC_VERTEX = /* glsl */ `
attribute vec4 aSpot;   // x, y, z, size (negative: flipped)
attribute vec4 aAxis;   // the card's up, then how far along it its anchor sits (0 its foot, 1 its top)
attribute vec4 aPlay;   // burst (-1: loops), delay, frames a second, shade
uniform float uAge[BURSTS];
uniform float uClock;
uniform float uNear;
uniform float uFar;
varying vec2 vCell;
varying float vAlpha;
varying float vShade;
${CELL}
void main() {
  float f;
  if (aPlay.x < 0.0) f = mod(floor(uClock * aPlay.z + aPlay.y * 64.0), 64.0);
  else {
    f = floor((uAge[int(aPlay.x)] - aPlay.y) * aPlay.z);
    if (f < 0.0 || f > 63.0) {
      gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
      return;
    }
  }
  vec4 centre = modelMatrix * vec4(aSpot.xyz, 1.0);
  vec3 up = normalize(mat3(modelMatrix) * aAxis.xyz);
  vec3 toEye = cameraPosition - centre.xyz;
  float dist = length(toEye);
  if (dist > uFar) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    return;
  }
  vec3 across = normalize(cross(up, toEye));
  float size = abs(aSpot.w);
  vec3 world = centre.xyz + across * (position.x - 0.5) * size + up * (position.y - aAxis.w) * size;
  gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
  vCell = cell(f, position.xy, aSpot.w);
  vAlpha = smoothstep(uNear * 0.3, uNear, dist) * smoothstep(uFar, uFar * 0.6, dist);
  vShade = aPlay.w;
}`;

/** A card's corners, 0 to 1. */
function quad(geometry: BufferGeometry) {
  geometry.setAttribute('position', new BufferAttribute(new Float32Array([0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 1, 0]), 3));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
}

/** A seeded random, so the cards are the same each ride. */
function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 16807) % 2147483647;
    return (s - 1) / 2147483646;
  };
}

function bookMaterial(vertexShader: string, tint: Color, cover: number, uniforms: Record<string, { value: unknown }>, defines?: Record<string, number>) {
  return new ShaderMaterial({
    vertexShader,
    fragmentShader: FRAGMENT,
    defines: defines ?? {},
    uniforms: {
      uMap: { value: null },
      uTint: { value: tint },
      uCover: { value: cover },
      uCurve: { value: new Vector2(0, 1) },
      uClock: { value: 0 },
      ...uniforms,
    },
    // (Spray's cards are mirrored for the bike's other side: seen from behind, then.)
    side: DoubleSide,
    transparent: true,
    depthWrite: false,
    // (Premultiplied: `uCover` 1 covers what's behind, as water and steam do, 0 adds, as sparks do. The buffer's alpha is left be.)
    blending: CustomBlending,
    blendEquation: AddEquation,
    blendSrc: OneFactor,
    blendDst: OneMinusSrcAlphaFactor,
    blendSrcAlpha: ZeroFactor,
    blendDstAlpha: OneFactor,
  });
}

function sprayCards(light: boolean) {
  const random = seeded(4711);
  const share = light ? 0.5 : 1;
  const places: number[] = [];
  const routes: number[] = [];
  const plays: number[] = [];
  // The bow wave, a low V from ahead of the bike out to the frame's edges (art/reference/concept-flooded-tunnel); under it, what fills the
  // corners by the bars; over it, the taller throws.
  const streams = [
    { n: 16, from: [11, 1.7], to: [0, 7.5], size: [2, 3.2], height: 0.8, shade: [0.55, 1], frame: 18 },
    { n: 18, from: [4.5, 1.7], to: [0.9, 1.9], size: [2.4, 3.8], height: 1, shade: [0.5, 1], frame: 8 },
    { n: 6, from: [9, 2.4], to: [0.5, 9], size: [2.6, 3.8], height: 0.85, shade: [0.4, 0.75], frame: 18 },
  ];
  for (const side of [-1, 1])
    for (const stream of streams) {
      const n = Math.round(stream.n * share);
      for (let i = 0; i < n; i++) {
        places.push(stream.from[0], stream.from[1] * (0.8 + random() * 0.4), stream.size[0] + random() * (stream.size[1] - stream.size[0]), side);
        routes.push(stream.to[0], stream.to[1] * (0.82 + random() * 0.36), stream.height, stream.frame);
        plays.push((i + random() * 0.8) / n, 0.85 + random() * 0.3, stream.shade[0] + random() * (stream.shade[1] - stream.shade[0]), 0);
      }
    }
  // The big splash: over the nose and up either side, once. (Rate here: of the book per second of its age.)
  const big = Math.round(18 * share);
  for (let i = 0; i < big; i++) {
    const side = i % 2 ? 1 : -1;
    const k = i / big;
    const ahead = 2.5 + 9 * random();
    const out = 0.4 + 4.6 * k;
    places.push(ahead, out, 5 + 7 * random(), side);
    routes.push(ahead - 7, out * 1.5, 1, 8);
    plays.push(-0.02 * (i % 4), 0.62 + random() * 0.2, 0.7 + random() * 0.3, 1);
  }
  const geometry = new InstancedBufferGeometry();
  quad(geometry);
  geometry.setAttribute('aPlace', new InstancedBufferAttribute(new Float32Array(places), 4));
  geometry.setAttribute('aRoute', new InstancedBufferAttribute(new Float32Array(routes), 4));
  geometry.setAttribute('aPlay', new InstancedBufferAttribute(new Float32Array(plays), 4));
  geometry.instanceCount = places.length / 4;
  const material = bookMaterial(
    SPRAY_VERTEX,
    new Color(1.0, 1.08, 1.04),
    1,
    {
      uAt: { value: new Vector3() },
      uAhead: { value: new Vector3(1, 0, 0) },
      uClock: { value: 0 },
      uAmount: { value: 0 },
      uSplash: { value: -1 },
      uSplashSize: { value: 1 },
      uNarrow: { value: 1 },
    },
    { GRAIN: 1 }
  );
  return { geometry, material };
}

type StaticCard = { at: readonly number[]; size: number; axis: readonly number[]; anchor: number; burst: number; delay: number; fps: number; shade: number };

function staticCards(cards: StaticCard[], tint: Color, cover: number, bursts: number, near: number, far: number) {
  const geometry = new InstancedBufferGeometry();
  quad(geometry);
  const spot = new Float32Array(cards.length * 4);
  const axis = new Float32Array(cards.length * 4);
  const play = new Float32Array(cards.length * 4);
  cards.forEach((c, i) => {
    spot.set([c.at[0], c.at[1], c.at[2], c.size], i * 4);
    axis.set([c.axis[0], c.axis[1], c.axis[2], c.anchor], i * 4);
    play.set([c.burst, c.delay, c.fps, c.shade], i * 4);
  });
  geometry.setAttribute('aSpot', new InstancedBufferAttribute(spot, 4));
  geometry.setAttribute('aAxis', new InstancedBufferAttribute(axis, 4));
  geometry.setAttribute('aPlay', new InstancedBufferAttribute(play, 4));
  geometry.instanceCount = cards.length;
  const material = bookMaterial(
    STATIC_VERTEX,
    tint,
    cover,
    { uAge: { value: new Float32Array(Math.max(bursts, 1)).fill(-1) }, uClock: { value: 0 }, uNear: { value: near }, uFar: { value: far } },
    { BURSTS: Math.max(bursts, 1) }
  );
  return { geometry, material };
}

const UP = [0, 1, 0] as const;

function steamCards(steam: SectionFxPlaces['steam'], light: boolean) {
  const cards: StaticCard[] = [];
  steam.forEach((e, burst) => {
    // The jet's way, in three's axes: its heading's Blender's, in the plan.
    const jet = [Math.cos(e.dir), 0.12, -Math.sin(e.dir)];
    const rising = [jet[0] * 0.55, 0.85, jet[2] * 0.55];
    const flat = [jet[0], 0.02, jet[2]];
    const all = [
      { axis: jet, size: 13, delay: 0, shade: 1 },
      { axis: flat, size: -10, delay: 0.1, shade: 0.8 },
      { axis: rising, size: 11, delay: 0.28, shade: 0.72 },
      { axis: jet, size: -15, delay: 0.42, shade: 0.6 },
      { axis: rising, size: -14, delay: 0.62, shade: 0.5 },
      { axis: UP, size: 12, delay: 0.85, shade: 0.42 },
    ];
    for (const c of light ? all.filter((_, i) => i % 2 === 0) : all) cards.push({ at: e.at, anchor: 0, burst, fps: 27, ...c });
  });
  return staticCards(cards, new Color('#d6ecda').multiplyScalar(0.62), 1, steam.length, 1.2, 90);
}

function sparkCards(sparks: SectionFxPlaces['sparks'], light: boolean) {
  const cards: StaticCard[] = [];
  sparks.forEach((e, burst) => {
    cards.push({ at: e.at, size: 9, axis: UP, anchor: 0.62, burst, delay: 0, fps: 30, shade: 1 });
    if (!light) cards.push({ at: e.at, size: -6.5, axis: UP, anchor: 0.6, burst, delay: 0.14, fps: 34, shade: 0.8 });
  });
  return staticCards(cards, new Color(3.6, 1.35, 0.32), 0, sparks.length, 1, 110);
}

function dripCards(drips: SectionFxPlaces['drips'], light: boolean) {
  const list = light ? drips.filter((_, i) => i % 2 === 0) : drips;
  const random = seeded(99);
  const cards = list.map((at) => ({ at, size: 4.6, axis: UP, anchor: 1, burst: -1, delay: random(), fps: 18, shade: 0.5 + 0.5 * random() }));
  return staticCards(cards, new Color(0.62, 0.86, 0.72), 0, 0, 1, 55);
}

const BOOK_PERIOD = 64 * 64;
const ahead = new Vector3();

type Book = { geometry: BufferGeometry; material: ShaderMaterial };

function Live({ road }: { road: Path }) {
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const scene = useThree((s) => s.scene);
  const root = useRef<Group>(null);
  const riding = useRef<Group>(null);
  const spray = useRef<Mesh>(null);
  const light = useMemo(isLightDevice, []);
  const places = useMemo(() => placeSectionFx(road), [road]);
  const books = useMemo(
    () => ({
      spray: sprayCards(light),
      steam: steamCards(places.steam, light),
      sparks: sparkCards(places.sparks, light),
      drips: dripCards(places.drips, light),
    }),
    [light, places]
  );
  const water = useMemo(() => makeWater(gl), [gl]);
  const state = useRef({
    last: -1,
    clock: 0,
    amount: 0,
    splash: -1,
    bornSteam: places.steam.map(() => -1),
    bornSparks: places.sparks.map(() => -1),
    dressed: { stair: null as Object3D | null, flood: null as Object3D | null },
  });
  const [ready, setReady] = useState(false);
  if (process.env.NODE_ENV === 'development' && typeof window !== 'undefined')
    (window as unknown as { __sectionFx?: unknown }).__sectionFx = { places, state, books, water, ride, doorState };

  useEffect(() => {
    const loader = new TextureLoader();
    const books_: [string, Book][] = [
      ['spray', books.spray],
      ['steam-burst', books.steam],
      ['sparks', books.sparks],
      ['drips', books.drips],
    ];
    const textures: Texture[] = [];
    let left = books_.length;
    for (const [name, book] of books_) {
      loader.load(`/textures/fx/${name}.png`, (t) => {
        t.colorSpace = NoColorSpace;
        t.minFilter = t.magFilter = LinearFilter;
        t.generateMipmaps = false;
        // (Up to the GPU now, not on the frame it's first seen.)
        gl.initTexture(t);
        book.material.uniforms.uMap.value = t;
        textures.push(t);
        if (--left === 0) {
          // (Their programs too, ahead of the frame they're first seen on.)
          if (root.current && riding.current) {
            precompile(gl, root.current, camera, scene);
            precompile(gl, riding.current, camera, scene);
          }
          setReady(true);
        }
      });
    }
    return () => {
      for (const t of textures) t.dispose();
      for (const [, book] of books_) {
        book.geometry.dispose();
        book.material.dispose();
      }
      water.dispose();
    };
  }, [books, gl, water, camera, scene]);

  useEffect(() => {
    loadSectionAudio();
    const again = () => loadSectionAudio();
    // (`?at=`'s context comes with the first press, after this.)
    window.addEventListener('pointerdown', again, { capture: true });
    return () => window.removeEventListener('pointerdown', again, { capture: true });
  }, []);

  // (After the camera's moved, ahead of the reflections and the composer.)
  useFrame(({ camera, clock, size }, delta) => {
    const leg = course.legs[4];
    const g = root.current;
    const r = riding.current;
    const f = state.current;
    if (!g || !r) return;
    const u = leg.placed && ride.zone === 4 ? ride.drive.s - leg.at : -1;
    const active = ready && u > places.from - 10 && u < places.to + 20;
    g.visible = r.visible = active;
    if (!active) {
      if (f.last >= 0) {
        f.last = -1;
        f.amount = 0;
        f.splash = -1;
        f.bornSteam.fill(-1);
        f.bornSparks.fill(-1);
      }
      updateSectionAudio(delta, false, 0, 0, 0);
      return;
    }
    const dt = Math.min(delta, 0.1);
    const t = clock.elapsedTime;
    const speed = ride.drive.speed;
    const spun = speed / 36;

    // The glbs' water: they come and go, a section at a time.
    for (let i = 0; i < SECTION_IDS.length; i++) {
      const id = SECTION_IDS[i];
      const held = sections.scene[id];
      if (f.dressed[id] !== held) {
        f.dressed[id] = held;
        held?.traverse(water.dress);
      }
    }

    g.position.copy(leg.origin);
    g.rotation.y = leg.yaw;
    camera.updateMatrixWorld();
    const e = camera.matrixWorld.elements;
    // Which way the bike's going: from the seat, not the road's data, so it's what's on screen.
    ahead.set(-e[8], 0, -e[10]).normalize();
    const waterY = leg.origin.y + places.level;

    // The water.
    const wu = water.material.uniforms;
    water.viewer.camera = camera;
    wu.uTime.value = t;
    (wu.uAxis.value as Vector3).copy(ahead);
    (wu.uEye.value as Vector3).copy(camera.position);
    wu.uCentre.value = waterY + TUBE.overWater;
    wu.uRadius.value = TUBE.radius;
    // (The door's plane until it's open; the far end of the room behind, after.)
    const toDoor = places.bulkhead - u;
    const open = doorOpen(2);
    wu.uEnd.value = toDoor > 0 ? toDoor + 60 * open : 1e4;
    wu.uDoor.value = toDoor;
    wu.uRed.value = (0.35 + 1.1 * open) * (1 - smoothstep(60, 420, toDoor));

    // Spray: from speed and where the road's in the water; at rest it settles.
    const want = ride.mount > 0.5 ? pathValue(road, road.spray, u) * Math.min(1.45, (speed / 28) ** 1.1) : 0;
    f.amount += (want - f.amount) * Math.min(1, dt * (want > f.amount ? 6 : 2.6));
    if (f.amount < 0.002) f.amount = 0;
    // (Each card's round takes half a second at the tunnel's speed.)
    f.clock = (f.clock + dt * 2.1 * Math.min(2.2, spun)) % BOOK_PERIOD;
    for (let i = 0; i < places.splashes.length; i++) {
      const splash = places.splashes[i];
      if (crossed(f.last, u, splash.s, speed)) {
        f.splash = 0;
        book(books.spray).uSplashSize.value = splash.size;
        playSectionSound(splash.sound);
      }
    }
    if (f.splash >= 0) {
      f.splash += dt;
      if (f.splash > 2.2) f.splash = -1;
    }
    const su = book(books.spray);
    (su.uAt.value as Vector3).set(camera.position.x, waterY, camera.position.z);
    (su.uAhead.value as Vector3).copy(ahead);
    su.uClock.value = f.clock;
    su.uAmount.value = f.amount;
    su.uSplash.value = f.splash;
    // (A tall frame's edges are nearer the bike: it's there the spray has to be seen.)
    su.uNarrow.value = Math.max(0.42, Math.min(1, size.width / size.height / 1.6));
    if (spray.current) spray.current.visible = f.amount > 0 || f.splash >= 0;

    // Steam across the road ahead, sparks over it, drips: by the distance along it. (Started ahead, to be at their height as the bike's there.)
    if (u < places.water + 20) {
      const age = book(books.steam).uAge.value as Float32Array;
      for (let i = 0; i < places.steam.length; i++) {
        if (crossed(f.last, u, places.steam[i].s - 26, speed)) {
          f.bornSteam[i] = t;
          playSectionSound(i % 2 ? 'steam-burst-short' : 'steam-burst', i % 2 ? 1 : 0.9);
        }
        age[i] = f.bornSteam[i] < 0 ? -1 : t - f.bornSteam[i];
      }
      const sparks = book(books.sparks).uAge.value as Float32Array;
      for (let i = 0; i < places.sparks.length; i++) {
        if (crossed(f.last, u, places.sparks[i].s - 20, speed)) f.bornSparks[i] = t;
        sparks[i] = f.bornSparks[i] < 0 ? -1 : t - f.bornSparks[i];
      }
      for (let i = 0; i < places.landings.length; i++) if (crossed(f.last, u, places.landings[i], speed)) sectionImpact('metal', 0.85);
    }
    book(books.drips).uClock.value = t % BOOK_PERIOD;

    // The sound.
    updateSectionAudio(dt, u >= places.water - 3 && u < places.waterTo + 6, Math.min(1, f.amount), ride.drive.rattle, spun);
    f.last = u;
  }, 0.3);

  return (
    <>
      {/* In the core's frame: what's in the tables. */}
      <group ref={root} visible={false}>
        <mesh geometry={books.steam.geometry} material={books.steam.material} frustumCulled={false} renderOrder={6} layers={NO_MIRROR_LAYER} />
        <mesh geometry={books.sparks.geometry} material={books.sparks.material} frustumCulled={false} renderOrder={7} layers={NO_MIRROR_LAYER} />
        <mesh geometry={books.drips.geometry} material={books.drips.material} frustumCulled={false} renderOrder={5} layers={NO_MIRROR_LAYER} />
      </group>
      {/* In the world: it goes with the bike. */}
      <group ref={riding} visible={false}>
        {/* (Only so its program's compiled with the rest.) */}
        <mesh visible={false} geometry={books.drips.geometry} material={water.material} />
        <mesh ref={spray} geometry={books.spray.geometry} material={books.spray.material} frustumCulled={false} renderOrder={6} layers={NO_MIRROR_LAYER} />
      </group>
    </>
  );
}

const book = (b: Book) => b.material.uniforms as Record<string, { value: unknown }>;
const SECTION_IDS = ['stair', 'flood'] as const;
/** Whether this frame's ride took it past `s`. (Not a jump along the road, or a stop just short.) */
const crossed = (last: number, u: number, s: number, speed: number) => last >= 0 && last < s && u >= s && u - last < 40 && speed > 2;

/** Mounted once. Past the lab's last stretch it fetches what it needs and stays; outside the sections it does nothing, and nothing's drawn. */
export function SectionFx() {
  const [road, setRoad] = useState<Path | null>(null);
  useFrame(() => {
    if (road) return;
    const leg = course.legs[4];
    if (ride.zone === 4 && leg.placed && leg.in && sections.spliced && ride.drive.s - leg.at > sections.stair.from - LOAD_AHEAD) setRoad(leg.in);
  });
  return road && !devFlag('nosectionfx') ? <Live key={sections.stair.from} road={road} /> : null;
}
