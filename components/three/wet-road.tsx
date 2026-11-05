'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import {
  BufferGeometry,
  type Camera,
  Color,
  Float32BufferAttribute,
  Frustum,
  type Group,
  type Material,
  Matrix4,
  type Object3D,
  type PerspectiveCamera,
  PlaneGeometry,
  Quaternion,
  type Scene,
  Vector3,
  type WebGLRenderer,
} from 'three';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { course, inLength, outLength, pathAt } from '@/lib/course';
import { hallShown } from '@/lib/doors';
import { devFlag, isLightDevice, journey, landingAt, NO_MIRROR_LAYER, pixelSize, smoothstep } from '@/lib/journey';
import { ride, road as street, TRANSITION_LEAD, zoneRoad } from '@/lib/ride';
import { sections } from '@/lib/sections';
import { AT } from './bike';

// The freeway's wet surface (as FogDrog's lake): three's Reflector renders the mirrored view, and this shader breaks it
// up the way rain on asphalt does: sharp in the puddles, smeared into long streaks toward the camera on the wet tarmac
// between them, shivering with the rain. The surface's own colour is near black.
export const RoadShader = {
  name: 'RoadShader',
  uniforms: {
    color: { value: null },
    tDiffuse: { value: null },
    textureMatrix: { value: null },
    uTime: { value: 0 },
    uAsphalt: { value: new Color('#070908') },
    // The bike's headlight on the road ahead (riding only): where it is, which way it points, how bright.
    uLamp: { value: new Vector3() },
    uLampDir: { value: new Vector3(1, 0, 0) },
    uLampOn: { value: 0 },
    // 0 the green city's wet asphalt, 1 the second city's road: a clean, unbroken mirror.
    uMirror: { value: 0 },
  },
  vertexShader: /* glsl */ `
    uniform mat4 textureMatrix;
    varying vec4 vUv;
    varying vec3 vWorld;
    void main() {
      vUv = textureMatrix * vec4(position, 1.0);
      vWorld = (modelMatrix * vec4(position, 1.0)).xyz;
      gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
    }`,
  fragmentShader: /* glsl */ `
    uniform sampler2D tDiffuse;
    uniform float uTime;
    uniform vec3 uAsphalt;
    uniform vec3 uLamp;
    uniform vec3 uLampDir;
    uniform float uLampOn;
    uniform float uMirror;
    varying vec4 vUv;
    varying vec3 vWorld;
    float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
    float vnoise(vec2 p) {
      vec2 i = floor(p), f = fract(p);
      vec2 u = f * f * (3.0 - 2.0 * f);
      return mix(mix(hash(i), hash(i + vec2(1, 0)), u.x), mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), u.x), u.y);
    }
    void main() {
      vec2 p = vWorld.xz;
      // Puddles: low spots in a soft noise field.
      float field = vnoise(p * 0.35) * 0.65 + vnoise(p * 1.3) * 0.35;
      float puddle = mix(smoothstep(0.5, 0.56, field), 1.0, uMirror);
      // Rain rings and the asphalt's grain shiver the reflection; on the tarmac it's smeared along the view (the long
      // streaks of light wet roads show), in the puddles barely touched.
      float grain = vnoise(p * vec2(18.0, 3.0) + uTime * 0.6) - 0.5;
      float rain = vnoise(p * 6.0 + uTime * 3.0) - 0.5;
      vec4 uv = vUv;
      uv.x += (grain * 0.05 * (1.0 - puddle) + rain * 0.006 * (1.0 - uMirror)) * uv.w;
      uv.y += (grain * 0.012 * (1.0 - puddle)) * uv.w;
      // The second city's mirror road is a skin of water, alive: long swells rolling across it, a finer shiver, and
      // drops landing here and there, their rings spreading. Together they bend the reflection.
      vec2 ripple = vec2(0.0);
      float rings = 0.0;
      if (uMirror > 0.0) {
        float e = 0.15;
        float h0 = vnoise(p * vec2(0.45, 0.9) + uTime * vec2(0.35, 0.6)) + 0.35 * vnoise(p * 2.6 - uTime * vec2(1.1, 0.4));
        float hx = vnoise((p + vec2(e, 0.0)) * vec2(0.45, 0.9) + uTime * vec2(0.35, 0.6)) + 0.35 * vnoise((p + vec2(e, 0.0)) * 2.6 - uTime * vec2(1.1, 0.4));
        float hz = vnoise((p + vec2(0.0, e)) * vec2(0.45, 0.9) + uTime * vec2(0.35, 0.6)) + 0.35 * vnoise((p + vec2(0.0, e)) * 2.6 - uTime * vec2(1.1, 0.4));
        ripple = vec2(hx - h0, hz - h0) / e;
        // Drops: in each 3 m cell, one landing every so often, its ring growing and fading.
        vec2 cell = floor(p / 3.0);
        vec2 at = (cell + 0.2 + 0.6 * vec2(hash(cell), hash(cell + 7.1))) * 3.0;
        float period = 1.6 + 2.4 * hash(cell + 3.3);
        float age = fract(uTime / period + hash(cell + 9.9));
        float r = distance(p, at);
        rings = sin((r - age * 2.4) * 9.0) * exp(-abs(r - age * 2.4) * 4.0) * (1.0 - age);
        ripple += normalize(p - at + 1e-4) * rings * 0.9;
        uv.xy += ripple * 0.011 * uMirror * uv.w;
      }
      vec3 sharp = texture2DProj(tDiffuse, uv).rgb;
      // The tarmac's reflection, stretched: a few taps down the view.
      vec3 smear = sharp;
      for (int i = 1; i < 5; i++) {
        vec4 t = uv;
        t.y += float(i) * 0.008 * t.w;
        smear += texture2DProj(tDiffuse, t).rgb;
      }
      smear /= 5.0;
      vec3 v = normalize(cameraPosition - vWorld);
      // (The mirror road reflects more at grazing angles, less looking down into it: water, not glass.)
      float fresnel = mix(0.04 + 0.96 * pow(1.0 - max(v.y, 0.0), 5.0), 0.35 + 0.45 * pow(1.0 - max(v.y, 0.0), 3.0), uMirror);
      vec3 reflection = mix(smear * 0.55, sharp * 1.05, puddle);
      vec3 col = mix(uAsphalt, reflection, fresnel * mix(0.75, 1.0, puddle));
      // Grit: the dry crowns of the aggregate catch nothing.
      col *= mix(1.0, 0.75 + 0.25 * hash(floor(p * 40.0)), 1.0 - puddle);
      col = mix(col, sharp, uMirror * 0.45);
      // Glints where the swells and rings catch the sky.
      col += vec3(1.0, 0.85, 0.95) * pow(max(0.0, length(ripple) * 0.35 + rings * 0.5), 3.0) * 0.6 * uMirror;
      // The headlight's pool: a cone widening down the road ahead of the bike, brightest in the puddles.
      if (uLampOn > 0.0) {
        vec2 d = vWorld.xz - uLamp.xz;
        float along = dot(d, uLampDir.xz);
        float side = dot(d, vec2(-uLampDir.z, uLampDir.x));
        float pool = exp(-pow(side / (0.4 + along * 0.32), 2.0)) * smoothstep(1.0, 5.0, along) * exp(-along / 22.0);
        col += vec3(0.75, 0.9, 0.7) * pool * uLampOn * mix(0.25, 0.6, puddle);
      }
      gl_FragColor = vec4(col, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
};

/** Riding on: the travelling mirror's in charge of the wet road. */
const riding = () => ride.mount > 0.5 && ride.drive.s > 1;

/**
 * A mirror's reflection is a whole second render of the scene. While the camera's still (the landing, mostly) it's
 * refreshed only every third frame (what it shows changes slowly: the rain and mist aren't in it, its ripples are in the
 * road's own shader); the moment the camera moves it's refreshed every frame.
 */
const AMORTISE_EVERY = 3;
function amortise(mirror: Reflector) {
  const render = mirror.onBeforeRender;
  const seen = { position: new Vector3(), quaternion: new Quaternion(), fov: 0, tick: 0, primed: false };
  mirror.onBeforeRender = function (renderer, scene, camera, geometry, material, group) {
    const c = camera as PerspectiveCamera;
    const moved =
      !seen.primed || seen.position.distanceToSquared(c.position) > 1e-6 || 1 - Math.abs(seen.quaternion.dot(c.quaternion)) > 1e-8 || seen.fov !== c.fov;
    seen.tick = (seen.tick + 1) % AMORTISE_EVERY;
    if (!moved && seen.tick !== 0) return;
    seen.position.copy(c.position);
    seen.quaternion.copy(c.quaternion);
    seen.fov = c.fov;
    seen.primed = true;
    render.call(this, renderer, scene, camera, geometry, material, group);
  };
}

/**
 * three looks up a lit material's program again whenever the light state it last drew under changes, and a render nested
 * inside another has a light state of its own. So a reflection left to Reflector's onBeforeRender, inside the frame's
 * render, sends everything lit through that lookup twice a frame, most of the ride's garbage. It's rendered here instead,
 * on its own just before the frame's: after everything's moved (0, the outline's 0.5), before the composer (1).
 */
const REFLECT_PRIORITY = 0.7;
const reflections = new WeakMap<Reflector, Reflector['onBeforeRender']>();
const inView = new Frustum();
const viewProjection = new Matrix4();
/** Takes a mirror's reflection out of the frame's render; it's what's rendered by reflect() from then on. */
function reflectionOf(mirror: Reflector) {
  let render = reflections.get(mirror);
  if (!render) {
    render = mirror.onBeforeRender;
    reflections.set(mirror, render);
    mirror.onBeforeRender = () => {};
  }
  return render;
}
function reflect(mirror: Reflector, gl: WebGLRenderer, scene: Scene, camera: Camera) {
  const render = reflectionOf(mirror);
  for (let o: Object3D | null = mirror; o; o = o.parent) if (!o.visible) return false;
  camera.updateMatrixWorld();
  mirror.updateWorldMatrix(true, false);
  if (mirror.frustumCulled) {
    inView.setFromProjectionMatrix(viewProjection.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse));
    if (!inView.intersectsObject(mirror)) return false;
  }
  // (A shadow redraw that's due belongs to the frame's render, as it did when this ran inside it.)
  const shadows = gl.shadowMap.needsUpdate;
  gl.shadowMap.needsUpdate = false;
  render.call(mirror, gl, scene, camera, mirror.geometry, mirror.material as Material, null as unknown as Group);
  gl.shadowMap.needsUpdate = shadows;
  return true;
}

export type DeckPlacement = { position: readonly [number, number, number]; heading: number; length: number; width: number };

export function WetRoad({ deck }: { deck: DeckPlacement }) {
  const road = useMemo(() => {
    const light = isLightDevice();
    const mirror = new Reflector(new PlaneGeometry(deck.length, deck.width), {
      // (Half the screen's resolution or less: the shader smears and ripples it anyway.)
      textureWidth: light ? 384 : 768,
      textureHeight: light ? 216 : 432,
      clipBias: 0.003,
      shader: RoadShader,
    });
    mirror.name = 'WetRoad';
    mirror.position.set(...deck.position);
    mirror.rotation.set(-Math.PI / 2, 0, deck.heading);
    amortise(mirror);
    return mirror;
  }, [deck]);
  useEffect(() => () => road.dispose(), [road]);

  useFrame((state) => {
    (road.material as unknown as { uniforms: { uTime: { value: number } } }).uniforms.uTime.value = state.clock.elapsedTime;
    // A mirror renders the whole scene again: only while the deck's actually in view (arriving at the landing, at it,
    // and riding along it), not on the way down or once the ride's left it behind.
    // (While riding, the mirror that travels with the bike takes over: RideMirror.)
    road.visible = landingAt(journey.frame) > 0.15 && !riding();
    // Its camera is a clone of the main one, layers and all: leave out the rain and mist (a full redraw of each, for
    // nothing the ripples would show).
    (road as Reflector & { getReflectionCamera: (c: Camera) => Camera }).getReflectionCamera(state.camera).layers.disable(NO_MIRROR_LAYER);
  });
  useFrame(({ gl, scene, camera }) => {
    reflect(road, gl, scene, camera);
  }, REFLECT_PRIORITY);

  return <primitive object={road} />;
}

// The wet road down the endless street: a strip of the same mirror that travels with the bike, from a little behind it
// to well ahead, along the road's centre line (its puddles and ripples are in world space, so they stay put on the road
// as the strip slides along under them).
const STRIP = { behind: 40, ahead: 420 };
/** In pixel mode the riding reflection needn't be sharper than this many of the frame's own pixels to each of its. */
const RIDE_REFLECTION_SCALE = 2.5;
const ahead = new Vector3();
const across = new Vector3();
const bikeLine = new Vector3();
/** The street's mirror, once it's rendered its reflection this frame: the chrome city's road, on the same plane, borrows it. */
let streetReflected: Reflector | null = null;
export function RideMirror() {
  const mirror = useMemo(() => {
    const light = isLightDevice();
    const m = new Reflector(new PlaneGeometry(STRIP.behind + STRIP.ahead, street.width - 1.1), {
      // (Lower than the landing's: it's re-rendered every frame while riding, and at speed the smear hides it.)
      textureWidth: light ? 320 : 576,
      textureHeight: light ? 180 : 324,
      clipBias: 0.003,
      shader: RoadShader,
      // (No edge smoothing for it in pixel mode: its edges are smeared, then pixelated.)
      multisample: pixelSize() ? 0 : 4,
    });
    m.name = 'RideMirror';
    m.visible = false;
    return m;
  }, []);
  useEffect(() => () => mirror.dispose(), [mirror]);

  useFrame((state) => {
    mirror.visible = street.known && riding();
    if (!mirror.visible) return;
    (mirror.material as unknown as { uniforms: { uTime: { value: number } } }).uniforms.uTime.value = state.clock.elapsedTime;
    (mirror as Reflector & { getReflectionCamera: (c: Camera) => Camera }).getReflectionCamera(state.camera).layers.disable(NO_MIRROR_LAYER);
    // Centred on the road line, abreast of the bike (how far it is past the deck's end; negative while still on it).
    // (In the second city it covers only its road's straight run in: past the bend its own wet floor takes over.)
    const tr = ride.transition;
    const first = course.legs[1];
    // (Up to where the chrome city's road begins: from there CityRoadMirror, laid along its curves, takes over.)
    const far = Math.min(ride.drive.s + STRIP.ahead, first.placed ? first.at : Number.POSITIVE_INFINITY);
    if (far - (STRIP.behind + STRIP.ahead) > ride.drive.s - 2 || ride.drive.s > far + 10) {
      mirror.visible = false;
      return;
    }
    const centreAt = far - (STRIP.behind + STRIP.ahead) / 2;
    ahead.copy(street.endCentre).addScaledVector(street.ahead, centreAt - street.end);
    // (The second city's road runs on the bike's line, not the deck's centre line: over its straight, follow that.)
    if (first.placed && centreAt > first.at) {
      across.set(-street.ahead.z, 0, street.ahead.x);
      ahead.addScaledVector(across, across.dot(bikeLine.set(AT[0], 0, AT[2]).sub(street.endCentre)));
    }
    mirror.position.set(ahead.x, -11 + 0.03, ahead.z);
    mirror.rotation.set(-Math.PI / 2, 0, street.yaw);
    const u = (mirror.material as unknown as { uniforms: Record<string, { value: unknown }> }).uniforms;
    (u.uLamp.value as Vector3).set(AT[0], AT[1], AT[2]).addScaledVector(street.ahead, ride.drive.s + 1);
    (u.uLampDir.value as Vector3).copy(street.ahead);
    const dusk = ride.zone === 1 ? tr.t : 1;
    u.uLampOn.value = Math.min(1, ride.drive.speed / 3 + (ride.drive.cruise ? 0.3 : 0)) * (1 - smoothstep(0.3, 0.65, dusk));
    // The road turns to the chrome city's pure mirror as that city comes to fill the view.
    u.uMirror.value = smoothstep(0.3, 0.65, dusk);
  });
  useFrame(({ gl, scene, camera, size, viewport }) => {
    // (Sized to the frame in pixel mode: the frame's far smaller than its full size, there. Only changes on a resize.)
    if (mirror.visible && pixelSize()) {
      const width = Math.ceil(size.width * viewport.dpr * RIDE_REFLECTION_SCALE);
      const height = Math.ceil(size.height * viewport.dpr * RIDE_REFLECTION_SCALE);
      const target = mirror.getRenderTarget();
      if (target.width !== width || target.height !== height) target.setSize(width, height);
    }
    streetReflected = mirror.visible && reflect(mirror, gl, scene, camera) ? mirror : null;
  }, REFLECT_PRIORITY);

  return <primitive object={mirror} />;
}

/**
 * A city's road as a mirror, all the way along its weave and on out: a ribbon on its centreline (flat, so one
 * reflection serves it all), in the city's own frame (a child of its group). The chrome city's a pure mirror, as the
 * ride's road has become by then; the hive's polished stone, less of one (`strength`).
 */
export function CityRoadMirror({ k, strength }: { k: number; strength: number }) {
  const mirror = useMemo(() => {
    const leg = course.legs[k];
    const into = zoneRoad(k);
    const half = 5.3;
    const positions: number[] = [];
    const index: number[] = [];
    const breaks: number[] = [];
    let hallIndex = 0;
    const lay = (p: { x: number; y: number; heading: number }) => {
      // (In the mirror's own plane, x and y; laid flat by turning it -90° about x, so its y is the road's local y.)
      const nx = -Math.sin(p.heading);
      const ny = Math.cos(p.heading);
      const n = positions.length / 6;
      positions.push(p.x + nx * half, p.y + ny * half, 0, p.x - nx * half, p.y - ny * half, 0);
      if (n > 0 && !breaks.includes(n)) {
        const a = 2 * (n - 1);
        index.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
      }
    };
    // (The core's starts past its gate tunnel, on the dusty road: the wet begins in the lab.)
    // (And it's flat, so none of it down the core's stairwell and tunnel: from the lab's doors on to the hall's start, below them.)
    const skipFrom = k === 4 && sections.spliced ? sections.stair.from : Number.POSITIVE_INFINITY;
    const skipTo = k === 4 && sections.spliced ? sections.hallFrom : Number.POSITIVE_INFINITY;
    let skipped = false;
    for (let u = k === 4 ? 136 : 0; u < into.length; u += 3) {
      if (u > skipFrom && u < skipTo) {
        // (The ribbon's cut there: no quad joins its two ends.)
        if (!skipped) {
          skipped = true;
          breaks.push(positions.length / 6);
          hallIndex = index.length;
        }
        continue;
      }
      lay(pathAt(into, u));
    }
    lay(pathAt(into, into.length));
    if (leg.out) for (let u = 3; u <= leg.out.length; u += 3) lay(pathAt(leg.out, u));
    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geometry.setIndex(index);
    const light = isLightDevice();
    const m = new Reflector(geometry, { textureWidth: light ? 320 : 576, textureHeight: light ? 180 : 324, clipBias: 0.003, shader: RoadShader });
    m.name = 'CityRoadMirror';
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.03;
    (m.material as unknown as { uniforms: { uMirror: { value: number } } }).uniforms.uMirror.value = strength;
    m.frustumCulled = false;
    // (Where the core's road's ribbon goes on past the cut, with the hall.)
    m.userData.hallIndex = hallIndex;
    return m;
  }, [k, strength]);
  useEffect(() => () => mirror.dispose(), [mirror]);
  useFrame((state) => {
    const leg = course.legs[k];
    const s = ride.drive.s;
    mirror.visible = leg.placed && s > leg.at - 300 && s < leg.at + inLength(leg) + outLength(leg) + 50 && !devFlag('nocitymirror');
    // (The core's: off past the lab's doors till the bulkhead's opened on the hall, then down there with it.)
    if (k === 4 && sections.spliced) {
      const u = s - leg.at;
      if (mirror.visible && u >= sections.stair.from && !hallShown(u)) mirror.visible = false;
      // (Only the hall's part of the ribbon's down there: the lab's would lie under the tunnel's red room.)
      const hall = hallShown(u);
      mirror.position.y = 0.03 - (hall ? sections.sink : 0);
      const cut = mirror.userData.hallIndex as number;
      if (hall) mirror.geometry.setDrawRange(cut, Number.POSITIVE_INFINITY);
      else mirror.geometry.setDrawRange(0, cut);
      // (From where the road's its own again, not the room: the flood's in sight till it's dropped.)
      if (hall && u < sections.hallFrom) mirror.visible = false;
    }
    if (!mirror.visible) return;
    const u = (mirror.material as unknown as { uniforms: { uTime: { value: number }; uMirror: { value: number } } }).uniforms;
    u.uTime.value = state.clock.elapsedTime;
    // (Going dull on the way out, ahead of the next city's road: it's gone by the join, the change's middle.)
    const end = leg.at + inLength(leg) + outLength(leg);
    // (The last zone has no way out: it stays.)
    u.uMirror.value = strength * (course.legs[k + 1] ? 1 - smoothstep(end - TRANSITION_LEAD - 80, end - 130, s) : 1);
    (mirror as Reflector & { getReflectionCamera: (c: Camera) => Camera }).getReflectionCamera(state.camera).layers.disable(NO_MIRROR_LAYER);
  });
  const toStreet = useMemo(() => new Matrix4(), []);
  useFrame(({ gl, scene, camera }) => {
    if (!mirror.visible) return;
    const u = (mirror.material as unknown as { uniforms: { tDiffuse: { value: unknown }; textureMatrix: { value: Matrix4 } } }).uniforms;
    // While the street's mirror is still under the bike, the chrome city's road lies on the same plane, seen from the same
    // camera: the one reflection serves both. (Only its texture matrix is its own: the street's, from its own frame.)
    if (k === 1 && streetReflected) {
      reflectionOf(mirror);
      mirror.updateWorldMatrix(true, false);
      const theirs = (streetReflected.material as unknown as { uniforms: { textureMatrix: { value: Matrix4 } } }).uniforms.textureMatrix.value;
      u.tDiffuse.value = streetReflected.getRenderTarget().texture;
      u.textureMatrix.value.copy(theirs).multiply(toStreet.copy(streetReflected.matrixWorld).invert()).multiply(mirror.matrixWorld);
    } else {
      u.tDiffuse.value = mirror.getRenderTarget().texture;
      reflect(mirror, gl, scene, camera);
    }
  }, REFLECT_PRIORITY + 0.1);
  return <primitive object={mirror} />;
}
