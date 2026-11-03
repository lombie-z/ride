import { AdditiveBlending, CanvasTexture, Color, DoubleSide, NormalBlending, ShaderMaterial, type Texture, Vector2 } from 'three';

// The map's looks (components/three/holomap.tsx): a slab of smoked black glass with its readouts, and on it the land in
// wireframe, the road and the markers, all in the zone's one phosphor. Seen through the pixel look, so nothing fine.

/** What they all share: the time, and how open the map is. */
export const holoShared = { uTime: { value: 0 }, uOpen: { value: 0 } };

const NOISE = /* glsl */ `
  float hash(float n) { return fract(sin(n) * 43758.5453); }
  float hash2(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }`;

/**
 * The slab: near-black (it has to hold over a blown-out sunset, as light added over one can't), cut to an uneven shape
 * with a notch over the projector. It powers on like a tube, from a white line; tears now and then, more when pointed at.
 */
export function panelMaterial(aspect: number) {
  return new ShaderMaterial({
    uniforms: {
      ...holoShared,
      uMap: { value: null as Texture | null },
      uAccent: { value: new Color() },
      uHover: { value: 0 },
      uAspect: { value: aspect },
    },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      void main() { vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform sampler2D uMap;
      uniform vec3 uAccent;
      uniform float uTime, uOpen, uHover, uAspect;
      varying vec2 vUv;
      ${NOISE}
      float cut(vec2 p, vec2 h, vec2 corner, float size) {
        return (dot(p, corner) - (dot(h, abs(corner)) - size)) * 0.7071;
      }
      void main() {
        // The tears: now and then a few bands of it slide sideways.
        float slot = floor(uTime * 7.0);
        float tearing = step(0.9 - 0.4 * uHover, hash(slot));
        float band = floor(vUv.y * 14.0);
        float tear = tearing * step(0.62, hash(band + slot)) * (hash(band * 3.1 + slot) - 0.5) * 0.07;
        vec2 uv = vUv + vec2(tear, 0.0);
        float split = 0.003 + 0.007 * uHover + 0.02 * tearing;

        // Its outline: the corners cut unevenly, a notch over the projector.
        vec2 p = (vUv - 0.5) * vec2(uAspect, 1.0);
        vec2 h = vec2(uAspect, 1.0) * 0.5;
        float d = max(abs(p.x) - h.x, abs(p.y) - h.y);
        d = max(d, cut(p, h, vec2(1.0, 1.0), 0.17));
        d = max(d, cut(p, h, vec2(-1.0, -1.0), 0.17));
        d = max(d, cut(p, h, vec2(-1.0, 1.0), 0.05));
        d = max(d, cut(p, h, vec2(1.0, -1.0), 0.05));
        d = max(d, -max(abs(p.x) - 0.1, abs(p.y + h.y) - 0.035));
        if (d > 0.0) discard;
        float rim = 1.0 - smoothstep(0.0, 0.016, -d);
        float inner = (1.0 - smoothstep(0.0, 0.01, abs(d + 0.03))) * 0.3;

        vec4 c = texture2D(uMap, uv);
        vec3 ink = vec3(texture2D(uMap, uv + vec2(split, 0.0)).r, c.g, texture2D(uMap, uv - vec2(split, 0.0)).b) * c.a;

        // A column of data rolling up its right edge.
        float data = 0.0;
        if (vUv.x > 0.885 && vUv.x < 0.965 && vUv.y > 0.17 && vUv.y < 0.72) {
          float row = floor(vUv.y * 40.0 - uTime * 3.0);
          float len = 0.25 + 0.75 * hash(row);
          data = step((vUv.x - 0.885) / 0.08, len) * step(0.3, fract(vUv.y * 40.0 - uTime * 3.0)) * step(0.25, hash(row * 1.7));
        }

        float scan = 0.82 + 0.18 * sin(vUv.y * 170.0 - uTime * 10.0);
        float flicker = 0.93 + 0.07 * hash(floor(uTime * 24.0));
        vec3 glass = vec3(0.004, 0.006, 0.007) + uAccent * 0.012 * (1.0 - vUv.y);
        vec3 light = ink * 1.5 * scan + uAccent * (rim * 1.8 + inner + data * 0.75 * scan);
        // Coming on: a white-hot line, cooling as it opens.
        float hot = 1.0 - smoothstep(0.1, 0.6, uOpen);
        vec3 col = glass + (light * flicker) + vec3(1.0) * hot * 3.0;
        gl_FragColor = vec4(col, 0.985);
        #include <colorspace_fragment>
      }`,
    transparent: true,
    blending: NormalBlending,
    depthWrite: false,
    depthTest: false,
    side: DoubleSide,
    toneMapped: false,
    fog: false,
  });
}

/** The land: a wire grid over its height, its contours brighter, a sweep rolling over it. */
export function terrainMaterial() {
  return new ShaderMaterial({
    uniforms: { ...holoShared, uAccent: { value: new Color() } },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      varying float vHeight;
      void main() {
        vUv = uv;
        vHeight = position.y;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uAccent;
      uniform float uTime;
      varying vec2 vUv;
      varying float vHeight;
      float wire(float v) { return 1.0 - min(abs(fract(v - 0.5) - 0.5) / fwidth(v), 1.0); }
      void main() {
        vec2 cells = vUv * vec2(16.0, 11.0);
        float grid = max(wire(cells.x), wire(cells.y));
        float contour = wire(vHeight * 170.0);
        vec2 e = min(vUv, 1.0 - vUv);
        float fade = smoothstep(0.0, 0.09, min(e.x, e.y));
        float high = smoothstep(-0.02, 0.022, vHeight);
        float sweep = smoothstep(0.86, 1.0, fract(vUv.y + uTime * 0.16));
        vec3 col = uAccent * (grid * (0.14 + 0.3 * high) + contour * (0.32 + 0.75 * high) + sweep * grid * 0.9);
        gl_FragColor = vec4(col * fade, 1.0);
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

/** The road: solid up to where you are, running dashes on to the next place, nothing past it (it's unknown). */
export function roadMaterial() {
  return new ShaderMaterial({
    uniforms: { ...holoShared, uAccent: { value: new Color() }, uHere: { value: 0 }, uNext: { value: 0 } },
    vertexShader: /* glsl */ `
      varying float vAlong;
      void main() { vAlong = uv.x; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uAccent;
      uniform float uTime, uHere, uNext;
      varying float vAlong;
      void main() {
        if (vAlong > uNext) discard;
        float on = vAlong <= uHere ? 1.0 : step(0.5, fract(vAlong * 34.0 - uTime * 1.6));
        if (on < 0.5) discard;
        float gone = vAlong <= uHere ? 1.0 : 1.0 - 0.5 * (vAlong - uHere) / max(uNext - uHere, 0.001);
        gl_FragColor = vec4(mix(uAccent, vec3(1.0), 0.25) * 1.7 * gone, 1.0);
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

function labelTexture(text: string) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const g = canvas.getContext('2d') as CanvasRenderingContext2D;
  g.font = 'bold 40px ui-monospace, Menlo, monospace';
  g.textAlign = 'center';
  g.textBaseline = 'middle';
  g.fillStyle = '#fff';
  g.fillText(text, 128, 34);
  return new CanvasTexture(canvas);
}

/** What a marker is: a place passed, where you are, the place ahead (no signal, until pointed at). */
export const MARKER = { passed: 0, here: 1, ahead: 2 } as const;

/** A marker, always facing the eye: `size` is its half width and height, in the camera's units. */
export function markerMaterial(kind: number, size: [number, number]) {
  return new ShaderMaterial({
    uniforms: {
      uTime: holoShared.uTime,
      uAccent: { value: new Color() },
      uAlert: { value: new Color('#ff2238') },
      uHover: { value: 0 },
      uKind: { value: kind },
      uSize: { value: new Vector2(...size) },
      uNoSignal: { value: kind === MARKER.ahead ? labelTexture('NO SIGNAL') : null },
      uLocked: { value: kind === MARKER.ahead ? labelTexture('LOCKED') : null },
    },
    vertexShader: /* glsl */ `
      uniform vec2 uSize;
      varying vec2 vP;
      void main() {
        vP = position.xy;
        vec4 c = modelViewMatrix * vec4(0.0, 0.0, 0.0, 1.0);
        c.xy += position.xy * uSize;
        gl_Position = projectionMatrix * c;
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uAccent, uAlert;
      uniform vec2 uSize;
      uniform float uTime, uHover, uKind;
      uniform sampler2D uNoSignal, uLocked;
      varying vec2 vP;
      ${NOISE}
      // The corners of a square turned by a, as brackets.
      float brackets(vec2 p, float a, float r, float w, float len) {
        float c = cos(a), s = sin(a);
        vec2 q = abs(mat2(c, -s, s, c) * p);
        float edge = max(q.x, q.y);
        float ring = step(r - w, edge) * step(edge, r);
        return ring * step(r - len, min(q.x, q.y));
      }
      void main() {
        vec3 col = vec3(0.0);
        float a = 0.0;
        float k = abs(vP.x) + abs(vP.y);
        if (uKind < 0.5) {
          // A place passed: a diamond (bracketed, and brighter, pointed at).
          float d = step(k, 0.42) * (0.55 + 0.45 * step(0.26, k));
          float lock = brackets(vP, uTime * 1.2, 1.0, 0.16, 0.45) * uHover;
          col = uAccent * (d * (1.4 + 2.0 * uHover) + lock * 2.6);
          a = max(d, lock);
        } else if (uKind < 1.5) {
          // Where you are: a reticle, its brackets slowly turning about a hot diamond, a pulse going out.
          float d = step(k, 0.2);
          float b = brackets(vP, uTime * 0.5, 0.9, 0.2, 0.5);
          float cross = step(min(abs(vP.x), abs(vP.y)), 0.035) * step(0.3, max(abs(vP.x), abs(vP.y))) * step(max(abs(vP.x), abs(vP.y)), 0.56);
          float t = fract(uTime * 0.7);
          float pulse = step(abs(length(vP) - t), 0.05) * (1.0 - t);
          col = uAccent * (b * 2.2 + cross * 1.4 + pulse * 1.0) + mix(uAccent, vec3(1.0), 0.6) * d * 3.0;
          // (On a dark disc, to read over the land.)
          a = max(max(d, b), max(max(cross, pulse), step(length(vP), 0.72) * 0.8));
        } else {
          // The place ahead: a block of static, hazard red, until pointed at, when it locks on in its own colour.
          vec2 cell = floor((vP + 1.0) * vec2(uSize.x / uSize.y, 1.0) * 7.0);
          float n = hash2(cell + floor(uTime * 12.0));
          float rain = step(0.86, fract(cell.y * 0.13 + uTime * (0.5 + hash(cell.x) * 1.4) + hash(cell.x * 3.7)));
          vec3 ink = mix(uAlert, uAccent, uHover);
          vec2 q = abs(vP);
          float frame = step(0.88, max(q.x, q.y * 1.0));
          vec2 luv = vec2(vP.x * 0.5 + 0.5, (vP.y + 0.0) * 1.15 + 0.5);
          float inside = step(abs(vP.y), 0.42);
          float label = inside * mix(texture2D(uNoSignal, luv).a, texture2D(uLocked, luv).a, step(0.5, uHover));
          col = vec3(0.005) + ink * ((n * 0.32 + rain * 0.6) * (1.0 - inside * 0.85) * (1.0 - 0.6 * uHover) + frame * 2.2) + mix(ink, vec3(1.0), 0.5) * label * 3.0;
          a = 0.92;
        }
        if (a <= 0.0) discard;
        gl_FragColor = vec4(col, a);
        #include <colorspace_fragment>
      }`,
    transparent: true,
    blending: NormalBlending,
    depthWrite: false,
    depthTest: false,
    side: DoubleSide,
    toneMapped: false,
    fog: false,
  });
}
