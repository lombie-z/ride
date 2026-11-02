'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo } from 'react';
import { Color, CylinderGeometry, DataTexture, DoubleSide, LinearFilter, RepeatWrapping, RGBAFormat, ShaderMaterial } from 'three';

// Mist and smog in the city below the deck, as in the concept: a green-grey pall pooled round the towers' feet, wisps
// drifting among them higher up, and a thin haze over the far skyline so its towers stand apart in layers. Each layer
// is a shell (an arc of a cylinder round the landing camera) at a fixed distance, so towers in front of it stay crisp
// and those behind it are veiled: stacked, the shells give the city depth. Their billows come from one tiling noise
// texture, sampled twice and drifted, rather than noise evaluated per pixel.

/** The landing camera (build-city.py EYE), the shells' centre. */
const EYE = { x: -37.16, z: 40.55 };
/** The towers' ground (build-city.py GROUND_Z). */
const GROUND_Y = -80;
// The arc the city fills, seen from the deck (build-city.py spreads the towers over +-62 degrees east).
const SPAN = 2.7;

/** Tiling fractal value noise, two independent fields (r, g), for the billows. */
function noiseTexture(size = 128) {
  const data = new Uint8Array(size * size * 4);
  const lattice = (seed: number, period: number) => {
    const values = new Float32Array(period * period);
    let s = seed;
    for (let i = 0; i < values.length; i++) {
      s = (s * 16807) % 2147483647;
      values[i] = s / 2147483647;
    }
    return (x: number, y: number) => {
      const ix = Math.floor(x);
      const iy = Math.floor(y);
      const fx = x - ix;
      const fy = y - iy;
      const ux = fx * fx * (3 - 2 * fx);
      const uy = fy * fy * (3 - 2 * fy);
      const at = (i: number, j: number) => values[(((j % period) + period) % period) * period + (((i % period) + period) % period)];
      const a = at(ix, iy) + (at(ix + 1, iy) - at(ix, iy)) * ux;
      const b = at(ix, iy + 1) + (at(ix + 1, iy + 1) - at(ix, iy + 1)) * ux;
      return a + (b - a) * uy;
    };
  };
  const fields = [0, 1].map((f) => [4, 8, 16, 32].map((period, o) => ({ n: lattice(9 + f * 101 + o * 17, period), period })));
  for (let y = 0; y < size; y++)
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      fields.forEach((octaves, f) => {
        let v = 0;
        let amp = 0.5;
        let total = 0;
        for (const { n, period } of octaves) {
          v += amp * n((x / size) * period, (y / size) * period);
          total += amp;
          amp *= 0.5;
        }
        data[i + f] = Math.round((v / total) * 255);
      });
      data[i + 2] = 0;
      data[i + 3] = 255;
    }
  const texture = new DataTexture(data, size, size, RGBAFormat);
  texture.wrapS = texture.wrapT = RepeatWrapping;
  texture.magFilter = texture.minFilter = LinearFilter;
  texture.needsUpdate = true;
  return texture;
}

const vertexShader = /* glsl */ `
varying vec3 vWorld;
varying float vAcross;
void main() {
  vAcross = uv.x;
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xyz;
  gl_Position = projectionMatrix * viewMatrix * world;
}`;

const fragmentShader = /* glsl */ `
uniform sampler2D uNoise;
uniform float uTime;
uniform float uOpacity;
uniform float uWidth;
uniform float uSeed;
uniform float uScale;
uniform float uPool;
uniform float uPoolTop;
uniform float uBand;
uniform float uBandY;
uniform float uBandW;
uniform float uHaze;
uniform float uHazeTop;
uniform vec3 uLow;
uniform vec3 uHigh;
varying vec3 vWorld;
varying float vAcross;
void main() {
  // Metres along the arc and up: billows stretched sideways (smog lies in layers), drifting slowly south.
  float along = vAcross * uWidth;
  vec2 q = vec2(along / (uScale * 2.2) + uTime * 0.0035 + uSeed, vWorld.y / uScale);
  vec4 n1 = texture2D(uNoise, q);
  vec4 n2 = texture2D(uNoise, q * vec2(3.1, 2.4) + vec2(-uTime * 0.006, uTime * 0.002) + uSeed * 0.37);
  float n = n1.r * 0.65 + n2.g * 0.35;
  float y = vWorld.y;
  // The pall round the towers' feet, its top heaped up and torn by the noise.
  float top = uPoolTop + (n1.g - 0.5) * uScale * 0.9;
  float pool = uPool * (1.0 - smoothstep(top - uScale * 0.35, top + uScale * 0.25, y));
  // Wisps among the towers: a band at some height, wavering.
  float bandAt = uBandY + (n1.g - 0.5) * uBandW * 1.6;
  float band = uBand * exp(-pow((y - bandAt) / uBandW, 2.0));
  float billow = smoothstep(0.26, 0.8, n + 0.12 * (pool / max(uPool, 0.001)));
  float d = (pool + band) * billow;
  // A thin even haze up to the skyline's heights (the far layers), with only a little structure.
  d += uHaze * (1.0 - smoothstep(GROUND_Y_ + 20.0, uHazeTop, y)) * (0.75 + 0.5 * n);
  // Feathered at the arc's ends, and off below the ground.
  d *= smoothstep(0.0, 0.14, vAcross) * smoothstep(1.0, 0.86, vAcross) * smoothstep(GROUND_Y_ - 2.0, GROUND_Y_ + 10.0, y);
  // Lit from below by the city: brighter, greener low down and where it's thick.
  float lit = (1.0 - smoothstep(GROUND_Y_, uPoolTop + uScale, y)) * 0.6 + n * 0.4;
  vec3 colour = mix(uHigh, uLow, clamp(lit, 0.0, 1.0));
  gl_FragColor = vec4(colour, clamp(d, 0.0, 1.0) * uOpacity);
  #include <colorspace_fragment>
}`.replace(/GROUND_Y_/g, GROUND_Y.toFixed(1));

interface Shell {
  /** Distance from the landing camera (m). */
  radius: number;
  /** The billows' size (m). */
  scale: number;
  pool: number;
  poolTop: number;
  band?: number;
  bandY?: number;
  bandW?: number;
  haze?: number;
  hazeTop?: number;
  /** The shell's top (m); it reaches down to the ground. */
  top: number;
}

// Near to far. Only the city above the deck's barrier is seen from the landing (about 3.4 degrees up from the eye), so
// each pool's top sits a little above that line at its distance, more so further off.
const SHELLS: Shell[] = [
  { radius: 205, scale: 30, pool: 0.85, poolTop: 22, band: 0.35, bandY: 52, bandW: 9, top: 90 },
  { radius: 300, scale: 40, pool: 0.8, poolTop: 38, band: 0.45, bandY: 88, bandW: 12, top: 130 },
  { radius: 450, scale: 55, pool: 0.75, poolTop: 58, band: 0.4, bandY: 130, bandW: 18, haze: 0.1, hazeTop: 180, top: 200 },
  { radius: 640, scale: 75, pool: 0.7, poolTop: 82, band: 0.35, bandY: 175, bandW: 26, haze: 0.16, hazeTop: 260, top: 290 },
  { radius: 900, scale: 100, pool: 0.65, poolTop: 110, band: 0.3, bandY: 230, bandW: 36, haze: 0.22, hazeTop: 340, top: 380 },
  { radius: 1250, scale: 140, pool: 0.6, poolTop: 140, haze: 0.3, hazeTop: 440, top: 480 },
];

// Green-grey smog: lighter and greener low down where the city lights it, darker above.
const LOW = new Color('#9cc2a3');
const HIGH = new Color('#3d5a47');

export function Mist({ light, opacity }: { light: boolean; opacity: { current: number } }) {
  const shells = useMemo(() => {
    const noise = noiseTexture();
    // Phones get the near pall, the mid wisps and the far haze; the in-between layers go.
    const chosen = light ? SHELLS.filter((_, i) => i % 2 === 0 || i === SHELLS.length - 1) : SHELLS;
    return chosen.map((s, i) => {
      const height = s.top - GROUND_Y;
      const geometry = new CylinderGeometry(s.radius, s.radius, height, light ? 32 : 64, 1, true, Math.PI / 2 - SPAN / 2, SPAN);
      const material = new ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms: {
          uNoise: { value: noise },
          uTime: { value: 0 },
          uOpacity: { value: 0 },
          uWidth: { value: s.radius * SPAN },
          uSeed: { value: i * 0.173 },
          uScale: { value: s.scale },
          uPool: { value: s.pool },
          uPoolTop: { value: s.poolTop },
          uBand: { value: s.band ?? 0 },
          uBandY: { value: s.bandY ?? 0 },
          uBandW: { value: s.bandW ?? 1 },
          uHaze: { value: s.haze ?? 0 },
          uHazeTop: { value: s.hazeTop ?? 0 },
          uLow: { value: LOW },
          uHigh: { value: HIGH },
        },
        side: DoubleSide,
        transparent: true,
        depthWrite: false,
        fog: false,
      });
      // Far to near (the beams, renderOrder 5, stand among the far layers: those draw before them, the near after).
      const renderOrder = s.radius > 420 ? 1 + (SHELLS.length - i) * 0.1 : 6 + i * 0.1;
      return { geometry, material, position: [EYE.x, GROUND_Y + height / 2, EYE.z] as const, renderOrder };
    });
  }, [light]);

  useFrame((state) => {
    for (const { material } of shells) {
      material.uniforms.uTime.value = state.clock.elapsedTime;
      material.uniforms.uOpacity.value = opacity.current;
    }
  });

  return (
    <>
      {shells.map(({ geometry, material, position, renderOrder }) => (
        <mesh key={material.uuid} name="Mist" geometry={geometry} material={material} position={position} renderOrder={renderOrder} frustumCulled={false} />
      ))}
    </>
  );
}
