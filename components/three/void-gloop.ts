import { useFrame } from '@react-three/fiber';
import { ShaderMaterial, Vector2, Vector3 } from 'three';
import { ride } from '@/lib/ride';

// The ooze as a window onto somewhere else (as Skirk's body shows a starfield in Genshin Impact): not lit or reflecting
// anything, it shows a layer of its own drawn in screen space, so it slides at its own rate as the camera moves rather
// than sitting on the surface. Here: deep red flowing like blood through the black, and eyes in it, opening and closing,
// looking toward the viewer.

const vertexShader = /* glsl */ `
varying vec3 vGloopNormal;
void main() {
  mat4 model = modelMatrix;
  #ifdef USE_INSTANCING
  model = modelMatrix * instanceMatrix;
  #endif
  vGloopNormal = normalize(mat3(viewMatrix) * mat3(model) * normal);
  gl_Position = projectionMatrix * viewMatrix * model * vec4(position, 1.0);
}`;

const fragmentShader = /* glsl */ `
uniform float uTime;
uniform vec2 uResolution;
uniform vec2 uDrift;
uniform vec2 uLook;
varying vec3 vGloopNormal;

float gHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float gNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(gHash(i), gHash(i + vec2(1, 0)), u.x), mix(gHash(i + vec2(0, 1)), gHash(i + vec2(1, 1)), u.x), u.y);
}
float gFbm(vec2 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { v += a * gNoise(p); p = p * 2.03 + 3.1; a *= 0.5; }
  return v;
}

// One eye in a cell: an almond of dim sclera, a blood-red iris, a black slit pupil; it blinks now and then.
vec3 eye(vec2 q, float seed, out float coverage) {
  coverage = 0.0;
  float open = smoothstep(0.0, 0.25, abs(sin(uTime * (0.25 + 0.3 * seed) + seed * 40.0))) ;
  open *= step(0.35, fract(seed * 7.3 + uTime * 0.05)) * 0.85 + 0.15;
  // The lids: an almond (two arcs), squeezing shut as it blinks.
  float h = 0.42 * open;
  float lid = abs(q.y) - h * (1.0 - q.x * q.x / 0.36);
  if (abs(q.x) > 0.6 || lid > 0.0) return vec3(0.0);
  coverage = smoothstep(0.0, -0.03, lid);
  vec2 iris = q - uLook * 0.18;
  float r = length(iris);
  vec3 c = vec3(0.32, 0.27, 0.22) * (1.0 - smoothstep(0.0, 0.6, abs(q.x)));
  float ring = gNoise(vec2(atan(iris.y, iris.x) * 6.0, r * 14.0));
  c = mix(c, mix(vec3(0.55, 0.02, 0.02), vec3(1.0, 0.25, 0.08), ring) * (1.0 - r * 2.5), smoothstep(0.24, 0.2, r));
  // A thin vertical slit pupil, and a wet glint.
  c = mix(c, vec3(0.0), smoothstep(0.05, 0.03, abs(iris.x)) * smoothstep(0.22, 0.16, abs(iris.y)));
  c += vec3(1.0, 0.85, 0.8) * smoothstep(0.045, 0.0, length(iris - vec2(-0.07, 0.08))) * 0.8;
  return c * coverage;
}

void main() {
  // Screen space, square cells, drifting slowly and sliding against the camera's turning (its own rate of motion).
  vec2 p = (gl_FragCoord.xy - 0.5 * uResolution) / uResolution.y + uDrift;
  // Blood: dark red welling and flowing downward through the black, in veins.
  vec2 flow = p * 3.0 + vec2(0.0, uTime * 0.35);
  float warp = gFbm(flow + gFbm(flow * 0.7 - uTime * 0.1));
  float veins = smoothstep(0.55, 0.8, warp) * (0.6 + 0.4 * gNoise(p * 40.0 + uTime));
  // (Deep: mostly near-black, the red welling in it.)
  vec3 c = vec3(0.11, 0.0, 0.005) * smoothstep(0.4, 0.8, warp) + vec3(0.42, 0.0, 0.015) * veins * veins;
  // Eyes, scattered sparsely through it.
  vec2 cell = floor(p * 4.0);
  vec2 local = fract(p * 4.0) - 0.5;
  float seed = gHash(cell);
  if (seed > 0.62) {
    float cov;
    vec2 jitter = (vec2(gHash(cell + 3.1), gHash(cell + 7.7)) - 0.5) * 0.3;
    vec3 e = eye((local - jitter) * (1.6 + seed), seed, cov);
    c = mix(c, e, cov);
  }
  // Shadowed toward its borders, where the gloop turns away: the red and the eyes sink into black at the edges.
  float facing = abs(normalize(vGloopNormal).z);
  c *= smoothstep(0.08, 0.75, facing);
  gl_FragColor = vec4(c, 1.0);
  #include <colorspace_fragment>
}`;

let shared: ShaderMaterial | null = null;
/** The one material for all the ooze (the slicks and the plaza's), updated once a frame by useVoidGloop. */
export function voidGloop() {
  if (shared) return shared;
  shared = new ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: { uTime: { value: 0 }, uResolution: { value: [1, 1] }, uDrift: { value: [0, 0] }, uLook: { value: [0, 0] } },
    fog: false,
  });
  return shared;
}

const forward = new Vector3();
/** Advances the ooze's other-world layer: its clock, the screen size, and its drift against the camera's turning. */
export function useVoidGloop() {
  useFrame((state) => {
    if (!shared) return;
    const u = shared.uniforms;
    u.uTime.value = state.clock.elapsedTime;
    const size = state.gl.getDrawingBufferSize(new Vector2());
    u.uResolution.value = [size.x, size.y];
    // Turning the camera slides the layer a fraction as far as the world moves: it's further off, somewhere else.
    state.camera.getWorldDirection(forward);
    u.uDrift.value = [Math.atan2(forward.x, forward.z) * 0.35 + state.clock.elapsedTime * 0.01, forward.y * 0.35];
    // The eyes follow the pointer (or the middle of the screen).
    const p = ride.pointer;
    u.uLook.value = p ? [(p.x / state.size.width) * 2 - 1, 1 - (p.y / state.size.height) * 2] : [0, 0];
  });
}
