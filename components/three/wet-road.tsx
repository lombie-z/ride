'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { BufferGeometry, type Camera, Color, Float32BufferAttribute, type PerspectiveCamera, PlaneGeometry, Quaternion, Vector3 } from 'three';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { isLightDevice, journey, landingAt, NO_MIRROR_LAYER, smoothstep } from '@/lib/journey';
import { cityRoadAt, cityRoadLength, ride, road as street } from '@/lib/ride';
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
      float fresnel = mix(0.04 + 0.96 * pow(1.0 - max(v.y, 0.0), 5.0), 0.92, uMirror);
      vec3 reflection = mix(smear * 0.55, sharp * 1.05, puddle);
      vec3 col = mix(uAsphalt, reflection, fresnel * mix(0.75, 1.0, puddle));
      // Grit: the dry crowns of the aggregate catch nothing.
      col *= mix(1.0, 0.75 + 0.25 * hash(floor(p * 40.0)), 1.0 - puddle);
      col = mix(col, sharp, uMirror * 0.85);
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

  return <primitive object={road} />;
}

// The wet road down the endless street: a strip of the same mirror that travels with the bike, from a little behind it
// to well ahead, along the road's centre line (its puddles and ripples are in world space, so they stay put on the road
// as the strip slides along under them).
const STRIP = { behind: 40, ahead: 420 };
const ahead = new Vector3();
const across = new Vector3();
const bikeLine = new Vector3();
export function RideMirror() {
  const mirror = useMemo(() => {
    const light = isLightDevice();
    const m = new Reflector(new PlaneGeometry(STRIP.behind + STRIP.ahead, street.width - 1.1), {
      // (Lower than the landing's: it's re-rendered every frame while riding, and at speed the smear hides it.)
      textureWidth: light ? 320 : 576,
      textureHeight: light ? 180 : 324,
      clipBias: 0.003,
      shader: RoadShader,
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
    // (Up to where the second city's road begins: from there CityRoadMirror, laid along its curves, takes over.)
    const far = Math.min(ride.drive.s + STRIP.ahead, tr.placed ? tr.at : Number.POSITIVE_INFINITY);
    if (far - (STRIP.behind + STRIP.ahead) > ride.drive.s - 2 || ride.drive.s > far + 10) {
      mirror.visible = false;
      return;
    }
    const centreAt = far - (STRIP.behind + STRIP.ahead) / 2;
    ahead.copy(street.endCentre).addScaledVector(street.ahead, centreAt - street.end);
    // (The second city's road runs on the bike's line, not the deck's centre line: over its straight, follow that.)
    if (tr.placed && centreAt > tr.at) {
      across.set(-street.ahead.z, 0, street.ahead.x);
      ahead.addScaledVector(across, across.dot(bikeLine.set(AT[0], 0, AT[2]).sub(street.endCentre)));
    }
    mirror.position.set(ahead.x, -11 + 0.03, ahead.z);
    mirror.rotation.set(-Math.PI / 2, 0, street.yaw);
    const u = (mirror.material as unknown as { uniforms: Record<string, { value: unknown }> }).uniforms;
    (u.uLamp.value as Vector3).set(AT[0], AT[1], AT[2]).addScaledVector(street.ahead, ride.drive.s + 1);
    (u.uLampDir.value as Vector3).copy(street.ahead);
    u.uLampOn.value = Math.min(1, ride.drive.speed / 3 + (ride.drive.cruise ? 0.3 : 0)) * (1 - smoothstep(0.3, 0.65, tr.t));
    // The road turns to the second city's pure mirror as that city comes to fill the view.
    u.uMirror.value = smoothstep(0.3, 0.65, tr.t);
  });

  return <primitive object={mirror} />;
}

/**
 * The second city's road as a mirror, all the way along its weave: a ribbon on its centreline (flat, so one reflection
 * serves it all), in the city's own frame (a child of its group). Pure mirror, as the ride's road has become by then.
 */
export function CityRoadMirror() {
  const mirror = useMemo(() => {
    const length = cityRoadLength();
    const half = 5.3;
    const n = Math.ceil(length / 3) + 1;
    const positions: number[] = [];
    const index: number[] = [];
    for (let i = 0; i < n; i++) {
      const p = cityRoadAt(Math.min(length, i * 3));
      // (In the mirror's own plane, x and y; laid flat by turning it -90° about x, so its y is the road's local y.)
      const nx = -Math.sin(p.heading);
      const ny = Math.cos(p.heading);
      positions.push(p.x + nx * half, p.y + ny * half, 0, p.x - nx * half, p.y - ny * half, 0);
      if (i > 0) {
        const a = 2 * (i - 1);
        index.push(a, a + 1, a + 2, a + 1, a + 3, a + 2);
      }
    }
    const geometry = new BufferGeometry();
    geometry.setAttribute('position', new Float32BufferAttribute(positions, 3));
    geometry.setIndex(index);
    const light = isLightDevice();
    const m = new Reflector(geometry, { textureWidth: light ? 320 : 576, textureHeight: light ? 180 : 324, clipBias: 0.003, shader: RoadShader });
    m.name = 'CityRoadMirror';
    m.rotation.x = -Math.PI / 2;
    m.position.y = 0.03;
    (m.material as unknown as { uniforms: { uMirror: { value: number } } }).uniforms.uMirror.value = 1;
    m.frustumCulled = false;
    return m;
  }, []);
  useEffect(() => () => mirror.dispose(), [mirror]);
  useFrame((state) => {
    const tr = ride.transition;
    mirror.visible = tr.placed && ride.drive.s > tr.at - 300;
    if (!mirror.visible) return;
    (mirror.material as unknown as { uniforms: { uTime: { value: number } } }).uniforms.uTime.value = state.clock.elapsedTime;
    (mirror as Reflector & { getReflectionCamera: (c: Camera) => Camera }).getReflectionCamera(state.camera).layers.disable(NO_MIRROR_LAYER);
  });
  return <primitive object={mirror} />;
}
