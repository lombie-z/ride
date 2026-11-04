import { wrapEffect } from '@react-three/postprocessing';
import { BlendFunction, Effect, EffectAttribute } from 'postprocessing';
import { Uniform } from 'three';

// Motion blur riding at speed: the world streaks out from where the road's heading (a zoom blur from a point a little
// above the middle of the screen), stronger toward the edges, while the bike itself, which moves with the camera, stays
// sharp: the bottom-middle of the screen, where it sits, is left out. Surging, an iridescent sheen comes in round the
// edges of the view too; launched from the slingshot, flames: tongues of fire streaming back past the view from its
// edges, the air shimmering with the heat.
const fragmentShader = /* glsl */ `
uniform float amount;
uniform float surge;
uniform float fire;
uniform float veins;
uniform float beat;
uniform float rush;
uniform vec2 focus;

float hash21(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}
float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash21(i), hash21(i + vec2(1.0, 0.0)), f.x), mix(hash21(i + vec2(0.0, 1.0)), hash21(i + vec2(1.0, 1.0)), f.x), f.y);
}
float fbm(vec2 p) {
  float v = 0.0;
  float a = 0.5;
  for (int i = 0; i < 4; i++) {
    v += a * noise(p);
    p = p * 2.03 + 11.7;
    a *= 0.5;
  }
  return v;
}

// Launched: flames round the view. In rays from the focus (the angle round it and the distance out), so they stream
// back past the rider as the world does, licking further in the stronger the launch; red at their tips, through orange
// to a yellow-white where they're thickest.
vec3 flames(vec2 toward, vec3 c) {
  if (fire <= 0.001) return c;
  float aspect = resolution.x / resolution.y;
  vec2 q = toward * vec2(aspect, 1.0);
  float r = length(q);
  float a = atan(q.y, q.x);
  // (The angle wraps at the back: blended across the seam so there's no line.)
  vec2 p = vec2(a * 2.2, r * 3.2 - time * 4.5);
  float n = fbm(vec2(p.x, p.y)) + 0.5 * fbm(vec2(p.x * 2.6 + 3.1, p.y * 1.7 - time * 2.0));
  float seam = smoothstep(2.6, 3.14159, abs(a));
  if (seam > 0.0) {
    vec2 p2 = vec2((a - sign(a) * 6.28318) * 2.2, p.y);
    float n2 = fbm(p2) + 0.5 * fbm(vec2(p2.x * 2.6 + 3.1, p2.y * 1.7 - time * 2.0));
    n = mix(n, n2, seam * 0.5);
  }
  float reach = mix(1.25, 0.66, fire);
  float heat = smoothstep(reach, reach + 0.5, r + (n - 0.75) * 0.8) * fire;
  // (Torn into tongues: gaps open between them, so it's flame, not a wall of light.)
  heat *= smoothstep(0.45, 0.85, n + 0.25 * heat);
  vec3 col = mix(vec3(0.45, 0.04, 0.01), vec3(1.0, 0.36, 0.05), smoothstep(0.05, 0.5, heat));
  col = mix(col, vec3(1.0, 0.72, 0.3), smoothstep(0.55, 0.95, heat));
  return c * (1.0 - 0.55 * heat) + col * heat * 1.15;
}

// Surging: a thin-film sheen creeping in from the edges of the view, its colours sliding round and shimmering.
vec3 iridescence(vec2 uv, vec2 toward, vec3 c) {
  if (surge <= 0.001) return c;
  float aspect = resolution.x / resolution.y;
  vec2 q = toward * vec2(aspect, 1.0);
  float r = length(q);
  float rim = smoothstep(0.42, 0.95, r) * surge;
  float a = atan(q.y, q.x);
  float band = a * 0.55 + r * 6.0 - time * 1.8 + sin(a * 5.0 + time * 2.3) * 0.35;
  vec3 film = 0.5 + 0.5 * cos(6.28318 * (vec3(0.0, 0.33, 0.67) + band));
  // Streaks of light racing out along the rim.
  float streak = pow(max(0.0, sin(a * 38.0 + time * 9.0)), 24.0) * smoothstep(0.55, 1.0, r);
  return c + (film * 0.55 + streak * 0.8) * rim;
}

// The hive's heartbeat: dark red veins branching in from the edges of the view, swelling and flushing on each beat, more
// of them the harder it's pumped; and the whole rim of the view flushing red with the beat.
vec3 heartbeat(vec2 toward, vec3 c) {
  if (veins <= 0.001) return c;
  float aspect = resolution.x / resolution.y;
  vec2 q = toward * vec2(aspect, 1.0);
  float r = length(q);
  float a = atan(q.y, q.x);
  // Ridged noise along the rays: thin branching lines, wandering as they come in.
  vec2 p = vec2(a * 3.0, r * 2.4);
  float n = noise(p * 2.0 + vec2(0.0, 0.3 * sin(time * 0.4))) * 0.6 + noise(p * 5.0) * 0.4;
  float ridge = pow(1.0 - abs(n * 2.0 - 1.0), 14.0);
  float reach = mix(1.05, 0.62, veins);
  float rim = smoothstep(reach, reach + 0.45, r);
  float swell = 0.55 + 0.9 * beat;
  vec3 blood = vec3(0.55, 0.02, 0.04);
  vec3 lines = blood * ridge * rim * swell * veins * 2.2;
  float flush = smoothstep(0.55, 1.25, r) * beat * (0.25 + 0.5 * veins);
  vec3 out3 = c * (1.0 - 0.35 * rim * veins - 0.3 * flush) + lines + vec3(0.45, 0.02, 0.05) * flush;
  if (rush <= 0.001) return out3;
  // Boosted: the rim thick with blood, and streaks of it racing back past the rider, gold where they're hottest, surging
  // on each beat.
  float wall = smoothstep(0.42, 1.0, r) * rush;
  float ray = pow(max(0.0, sin(a * 46.0 + 3.0 * sin(a * 7.0))), 10.0) * (0.45 + 0.55 * noise(vec2(a * 22.0, r * 5.0 - time * 8.0)));
  float bolt = ray * smoothstep(0.34, 0.95, r) * rush * (0.8 + 0.9 * beat);
  vec3 streak = mix(vec3(0.95, 0.05, 0.05), vec3(1.0, 0.72, 0.25), smoothstep(0.35, 0.9, ray));
  return out3 * (1.0 - 0.45 * wall) + vec3(0.5, 0.01, 0.03) * wall * (0.6 + 0.6 * beat) + streak * bolt * 1.5;
}

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  if (amount <= 0.001 && surge <= 0.001 && fire <= 0.001 && veins <= 0.001) {
    outputColor = inputColor;
    return;
  }
  vec2 toward = uv - focus;
  float edge = smoothstep(0.12, 0.75, length(toward * vec2(resolution.x / resolution.y, 1.0)));
  // The bike: an oval at the bottom middle.
  vec2 b = (uv - vec2(0.5, 0.0)) / vec2(0.26, 0.42);
  float bike = 1.0 - smoothstep(0.75, 1.0, length(b));
  float k = amount * edge * (1.0 - bike);
  // (Launched, the air shimmers with the heat toward the edges.)
  vec2 at = uv;
  if (fire > 0.001) at += (vec2(noise(uv * 18.0 + vec2(0.0, -time * 6.0)), noise(uv * 18.0 + vec2(7.3, -time * 6.0))) - 0.5) * 0.012 * fire * edge;
  vec3 sum = fire > 0.001 ? texture2D(inputBuffer, at).rgb : inputColor.rgb;
  if (k < 0.002) {
    outputColor = vec4(heartbeat(toward, flames(toward, iridescence(uv, toward, sum))), inputColor.a);
    return;
  }
  float jitter = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453);
  for (int i = 1; i < 10; i++) {
    float t = (float(i) + jitter) / 10.0;
    sum += texture2D(inputBuffer, at - toward * k * 0.09 * t).rgb;
  }
  outputColor = vec4(heartbeat(toward, flames(toward, iridescence(uv, toward, sum / 10.0))), inputColor.a);
}`;

export class SpeedBlurEffect extends Effect {
  constructor() {
    super('SpeedBlurEffect', fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      attributes: EffectAttribute.CONVOLUTION,
      uniforms: new Map<string, Uniform>([
        ['amount', new Uniform(0)],
        ['surge', new Uniform(0)],
        ['fire', new Uniform(0)],
        ['veins', new Uniform(0)],
        ['beat', new Uniform(0)],
        ['rush', new Uniform(0)],
        ['focus', new Uniform([0.5, 0.58])],
      ]),
    });
  }

  /** How strong the blur is (from the speed), the surge, the slingshot's flames, the heartbeat's veins and its boost (0 to 1). */
  set(amount: number, surge = 0, fire = 0, veins = 0, beat = 0, rush = 0) {
    (this.uniforms.get('amount') as Uniform<number>).value = amount;
    (this.uniforms.get('surge') as Uniform<number>).value = surge;
    (this.uniforms.get('fire') as Uniform<number>).value = fire;
    (this.uniforms.get('veins') as Uniform<number>).value = veins;
    (this.uniforms.get('beat') as Uniform<number>).value = beat;
    (this.uniforms.get('rush') as Uniform<number>).value = rush;
  }
}

export const SpeedBlur = wrapEffect(SpeedBlurEffect);
