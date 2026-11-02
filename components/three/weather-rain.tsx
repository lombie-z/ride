'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo } from 'react';
import { AdditiveBlending, BufferAttribute, BufferGeometry, Color, InstancedBufferAttribute, InstancedBufferGeometry, ShaderMaterial, Vector2 } from 'three';

// Rain at the landing: fine streaks falling round the camera, and splash flecks on the deck in front of it.
// The streaks are instanced quads, each a drop's motion blur: its head and tail projected and joined by a thin
// screen-space ribbon, so it stays a hairline at any distance. Drops live in a box of space round the camera that
// tiles the world (each wraps within it), so they're fixed in the world while the camera moves. All on the GPU.

const DECK_Y = -11;
// The deck's extent (build-city.py DECK_X, DECK_Y; three's z is Blender's -y), for the splashes.
const DECK = { x: [-60, -12], z: [-14, 6.5] } as const;
// A slight wind from behind and to the left.
const VELOCITY = [0.9, -9.5, 0.4] as const;
// Two boxes of falling rain round the camera (m), from the deck up and pushed ahead of the camera (it looks east): a
// close one, and a big sparse one whose streaks hang over the city in sheets.
const NEAR = { box: [34, 16, 34], ahead: 9, length: 0.045, opacity: 0.55, from: [0.6, 2] } as const;
const FAR = { box: [110, 60, 110], ahead: 40, length: 0.07, opacity: 0.45, from: [10, 18] } as const;
type Layer = typeof NEAR | typeof FAR;
const RAIN_COLOUR = new Color(0.62, 0.86, 0.66);

const rainVertex = /* glsl */ `
attribute vec3 aSeed;
uniform float uTime;
uniform vec3 uVelocity;
uniform vec3 uBox;
uniform vec3 uLow;
uniform float uLength;
uniform vec2 uResolution;
uniform float uWidth;
uniform vec2 uFrom;
varying float vAlpha;
varying vec2 vQuad;
void main() {
  // Each drop falls at its own speed through the box, wrapping within it.
  vec3 v = uVelocity * (0.8 + 0.4 * aSeed.y);
  vec3 p = uLow + mod(aSeed * uBox * 7.31 + v * uTime - uLow, uBox);
  vec3 tail = p - v * uLength;
  vec4 h = projectionMatrix * viewMatrix * vec4(p, 1.0);
  vec4 t = projectionMatrix * viewMatrix * vec4(tail, 1.0);
  if (h.w < 0.25 || t.w < 0.25) { gl_Position = vec4(0.0, 0.0, 2.0, 1.0); return; }
  vec2 sh = h.xy / h.w * uResolution;
  vec2 st = t.xy / t.w * uResolution;
  vec2 dir = sh - st;
  float len = length(dir);
  dir = len > 1e-3 ? dir / len : vec2(0.0, 1.0);
  vec2 across = vec2(-dir.y, dir.x);
  // position.x: -1/1 across the streak, position.y: 0 at the head, 1 at the tail (plus half a width of cap each end).
  vec4 c = mix(h, t, position.y);
  vec2 offset = across * position.x * uWidth + dir * (0.5 - position.y) * 2.0 * uWidth;
  c.xy += offset / uResolution * c.w;
  gl_Position = c;
  vQuad = position.xy;
  // Faded in close (they'd be blurs) and toward the box's edges (so the wrap is never seen), and thinner far off.
  float dist = h.w;
  vAlpha = smoothstep(uFrom.x, uFrom.y, dist) * (1.0 - smoothstep(uBox.x * 0.32, uBox.x * 0.5, dist));
  vAlpha *= clamp(2.5 / dist, 0.25, 1.0) * (0.6 + 0.4 * aSeed.z);
}`;

const rainFragment = /* glsl */ `
uniform vec3 uColour;
uniform float uOpacity;
varying float vAlpha;
varying vec2 vQuad;
void main() {
  // Soft across, brightest toward the head.
  float across = 1.0 - abs(vQuad.x);
  float a = across * across * mix(1.0, 0.35, clamp(vQuad.y, 0.0, 1.0));
  gl_FragColor = vec4(uColour * a * vAlpha * uOpacity, 1.0);
  #include <colorspace_fragment>
}`;

function rain(count: number, layer: Layer) {
  const geometry = new InstancedBufferGeometry();
  // A quad from head (y 0) to tail (y 1), a unit wide either side.
  geometry.setAttribute('position', new BufferAttribute(new Float32Array([-1, 0, 0, 1, 0, 0, 1, 1, 0, -1, 1, 0]), 3));
  geometry.setIndex([0, 1, 2, 0, 2, 3]);
  const seed = new Float32Array(count * 3);
  for (let i = 0; i < seed.length; i++) seed[i] = Math.random();
  geometry.setAttribute('aSeed', new InstancedBufferAttribute(seed, 3));
  geometry.instanceCount = count;
  const material = new ShaderMaterial({
    vertexShader: rainVertex,
    fragmentShader: rainFragment,
    uniforms: {
      uTime: { value: 0 },
      uVelocity: { value: VELOCITY },
      uBox: { value: layer.box },
      uLow: { value: [0, DECK_Y, 0] },
      // Seconds of travel each streak shows (a camera's motion blur).
      uLength: { value: layer.length },
      uResolution: { value: new Vector2(1, 1) },
      uWidth: { value: 0.75 },
      uFrom: { value: layer.from },
      uColour: { value: RAIN_COLOUR },
      uOpacity: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
  });
  return { geometry, material, layer };
}

const splashVertex = /* glsl */ `
attribute float aId;
uniform float uTime;
uniform float uScale;
uniform vec2 uCentre;
uniform vec4 uArea;
varying float vK;
varying float vSeed;
varying float vFlat;
float sHash(float n) { return fract(sin(n) * 43758.5453); }
void main() {
  // Each splash lives briefly and comes back somewhere new: where is a hash of its cycle.
  float life = 0.32 + 0.12 * sHash(aId * 1.7);
  float tt = uTime / life + sHash(aId * 3.1);
  float cycle = floor(tt);
  vK = fract(tt);
  vSeed = sHash(aId + cycle * 13.7);
  // Mostly close to the camera (most of the deck seen), thinning out ahead.
  float r = pow(sHash(aId * 5.3 + cycle * 7.1), 1.6);
  float a = (sHash(aId * 9.7 + cycle * 3.3) - 0.5) * 1.9;
  vec2 xz = uCentre + vec2(cos(a), sin(a)) * (0.6 + r * 14.0);
  xz = clamp(xz, uArea.xy, uArea.zw);
  vec3 p = vec3(xz.x, ${DECK_Y.toFixed(2)} + 0.01, xz.y);
  vec4 mv = viewMatrix * vec4(p, 1.0);
  gl_Position = projectionMatrix * mv;
  float dist = -mv.z;
  gl_PointSize = 0.16 * uScale * projectionMatrix[1][1] / dist;
  // How flat the ring looks: the deck seen edge-on from eye height.
  vFlat = clamp(abs(cameraPosition.y - p.y) / dist, 0.08, 1.0);
}`;

const splashFragment = /* glsl */ `
uniform vec3 uColour;
uniform float uOpacity;
varying float vK;
varying float vSeed;
varying float vFlat;
void main() {
  vec2 q = (gl_PointCoord - 0.5) * 2.0;
  q.y = -q.y;
  // A ring spreading on the deck (an ellipse, the deck seen at a slant) and a little crown of flecks thrown up.
  vec2 e = vec2(q.x, (q.y + 0.6) / max(vFlat, 0.12));
  float radius = 0.15 + 0.65 * sqrt(vK);
  float ring = 1.0 - smoothstep(0.0, 0.09, abs(length(e) - radius));
  ring *= step(q.y, -0.2);
  float crown = 0.0;
  for (int i = 0; i < 3; i++) {
    float fi = float(i);
    float x = (fi - 1.0) * 0.32 * (0.4 + vK) + (vSeed - 0.5) * 0.2;
    float h = -0.6 + 2.2 * vK * (1.0 - vK) * (1.0 - 0.3 * abs(fi - 1.0));
    crown += 1.0 - smoothstep(0.05, 0.12, length(q - vec2(x, h)));
  }
  float a = (ring + crown) * 1.8 * (1.0 - vK) * (1.0 - vK);
  if (a < 0.002) discard;
  gl_FragColor = vec4(uColour * a * uOpacity, 1.0);
  #include <colorspace_fragment>
}`;

function splashes(count: number) {
  const geometry = new BufferGeometry();
  geometry.setAttribute('position', new BufferAttribute(new Float32Array(count * 3), 3));
  geometry.setAttribute(
    'aId',
    new BufferAttribute(
      Float32Array.from({ length: count }, (_, i) => i + 1),
      1
    )
  );
  const material = new ShaderMaterial({
    vertexShader: splashVertex,
    fragmentShader: splashFragment,
    uniforms: {
      uTime: { value: 0 },
      uScale: { value: 1 },
      uCentre: { value: new Vector2() },
      uArea: { value: [DECK.x[0] + 0.5, DECK.z[0] + 0.5, DECK.x[1] - 0.6, DECK.z[1] - 0.6] },
      uColour: { value: RAIN_COLOUR },
      uOpacity: { value: 0 },
    },
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
  });
  return { geometry, material };
}

export function Rain({ light, opacity }: { light: boolean; opacity: { current: number } }) {
  const layers = useMemo(() => [rain(light ? 2600 : 7000, NEAR), rain(light ? 1500 : 5000, FAR)], [light]);
  const flecks = useMemo(() => splashes(light ? 110 : 260), [light]);

  useFrame((state) => {
    const { camera, clock, gl } = state;
    const time = clock.elapsedTime;
    for (const { material, layer } of layers) {
      const u = material.uniforms;
      u.uTime.value = time;
      // (In drawing-buffer pixels: NDC spans two units.)
      const size = gl.getDrawingBufferSize(u.uResolution.value as Vector2);
      size.multiplyScalar(0.5);
      // In pixel mode's low resolution each streak is a fat pixel wide: fainter, so the rain doesn't turn to bars.
      u.uOpacity.value = opacity.current * layer.opacity * Math.min(1, Math.max(0.6, size.y / 360));
      // Hairlines, a pixel or so wide: at pixel mode's low resolution that's a chunky pixel streak, as everything else.
      u.uWidth.value = Math.max(0.6, Math.min(1.1, size.y / 500));
      const low = u.uLow.value as number[];
      low[0] = camera.position.x - layer.box[0] / 2 + layer.ahead;
      low[2] = camera.position.z - layer.box[2] / 2;
    }

    const s = flecks.material.uniforms;
    s.uTime.value = time;
    s.uOpacity.value = opacity.current;
    s.uScale.value = state.size.height * state.viewport.dpr * 0.5;
    // Ahead of the camera, on the deck.
    (s.uCentre.value as Vector2).set(camera.position.x + 0.5, camera.position.z);
  });

  return (
    <>
      {layers.map(({ geometry, material }) => (
        <mesh key={material.uuid} name="Rain" geometry={geometry} material={material} frustumCulled={false} renderOrder={10} />
      ))}
      <points name="RainSplashes" geometry={flecks.geometry} material={flecks.material} frustumCulled={false} renderOrder={10} />
    </>
  );
}
