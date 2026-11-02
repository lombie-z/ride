import { wrapEffect } from '@react-three/postprocessing';
import { BlendFunction, Effect, EffectAttribute } from 'postprocessing';
import { Uniform } from 'three';

// Motion blur riding at speed: the world streaks out from where the road's heading (a zoom blur from a point a little
// above the middle of the screen), stronger toward the edges, while the bike itself, which moves with the camera, stays
// sharp: the bottom-middle of the screen, where it sits, is left out. Surging, an iridescent sheen comes in round the
// edges of the view too.
const fragmentShader = /* glsl */ `
uniform float amount;
uniform float surge;
uniform vec2 focus;

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

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  if (amount <= 0.001 && surge <= 0.001) {
    outputColor = inputColor;
    return;
  }
  vec2 toward = uv - focus;
  float edge = smoothstep(0.12, 0.75, length(toward * vec2(resolution.x / resolution.y, 1.0)));
  // The bike: an oval at the bottom middle.
  vec2 b = (uv - vec2(0.5, 0.0)) / vec2(0.26, 0.42);
  float bike = 1.0 - smoothstep(0.75, 1.0, length(b));
  float k = amount * edge * (1.0 - bike);
  vec3 sum = inputColor.rgb;
  if (k < 0.002) {
    outputColor = vec4(iridescence(uv, toward, sum), inputColor.a);
    return;
  }
  float jitter = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453);
  for (int i = 1; i < 10; i++) {
    float t = (float(i) + jitter) / 10.0;
    sum += texture2D(inputBuffer, uv - toward * k * 0.09 * t).rgb;
  }
  outputColor = vec4(iridescence(uv, toward, sum / 10.0), inputColor.a);
}`;

export class SpeedBlurEffect extends Effect {
  constructor() {
    super('SpeedBlurEffect', fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      attributes: EffectAttribute.CONVOLUTION,
      uniforms: new Map<string, Uniform>([
        ['amount', new Uniform(0)],
        ['surge', new Uniform(0)],
        ['focus', new Uniform([0.5, 0.58])],
      ]),
    });
  }

  /** How strong the blur is (from the speed) and the surge (0 to 1). */
  set(amount: number, surge = 0) {
    (this.uniforms.get('amount') as Uniform<number>).value = amount;
    (this.uniforms.get('surge') as Uniform<number>).value = surge;
  }
}

export const SpeedBlur = wrapEffect(SpeedBlurEffect);
