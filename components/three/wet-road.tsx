'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo } from 'react';
import { type Camera, Color, PlaneGeometry } from 'three';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { isLightDevice, journey, landingAt, NO_MIRROR_LAYER } from '@/lib/journey';
import { ride, road as street } from '@/lib/ride';

// The freeway's wet surface (as FogDrog's lake): three's Reflector renders the mirrored view, and this shader breaks it
// up the way rain on asphalt does: sharp in the puddles, smeared into long streaks toward the camera on the wet tarmac
// between them, shivering with the rain. The surface's own colour is near black.
const RoadShader = {
  name: 'RoadShader',
  uniforms: {
    color: { value: null },
    tDiffuse: { value: null },
    textureMatrix: { value: null },
    uTime: { value: 0 },
    uAsphalt: { value: new Color('#070908') },
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
      float puddle = smoothstep(0.5, 0.56, field);
      // Rain rings and the asphalt's grain shiver the reflection; on the tarmac it's smeared along the view (the long
      // streaks of light wet roads show), in the puddles barely touched.
      float grain = vnoise(p * vec2(18.0, 3.0) + uTime * 0.6) - 0.5;
      float rain = vnoise(p * 6.0 + uTime * 3.0) - 0.5;
      vec4 uv = vUv;
      uv.x += (grain * 0.05 * (1.0 - puddle) + rain * 0.006) * uv.w;
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
      float fresnel = 0.04 + 0.96 * pow(1.0 - max(v.y, 0.0), 5.0);
      vec3 reflection = mix(smear * 0.55, sharp * 1.05, puddle);
      vec3 col = mix(uAsphalt, reflection, fresnel * mix(0.75, 1.0, puddle));
      // Grit: the dry crowns of the aggregate catch nothing.
      col *= mix(1.0, 0.75 + 0.25 * hash(floor(p * 40.0)), 1.0 - puddle);
      gl_FragColor = vec4(col, 1.0);
      #include <tonemapping_fragment>
      #include <colorspace_fragment>
    }`,
};

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
    return mirror;
  }, [deck]);
  useEffect(() => () => road.dispose(), [road]);

  useFrame((state) => {
    (road.material as unknown as { uniforms: { uTime: { value: number } } }).uniforms.uTime.value = state.clock.elapsedTime;
    // A mirror renders the whole scene again: only while the deck's actually in view (arriving at the landing, at it,
    // and riding along it), not on the way down or once the ride's left it behind.
    road.visible = landingAt(journey.frame) > 0.15 && ride.drive.s < street.end + 25;
    // Its camera is a clone of the main one, layers and all: leave out the rain and mist (a full redraw of each, for
    // nothing the ripples would show).
    (road as Reflector & { getReflectionCamera: (c: Camera) => Camera }).getReflectionCamera(state.camera).layers.disable(NO_MIRROR_LAYER);
  });

  return <primitive object={road} />;
}
