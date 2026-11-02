import { wrapEffect } from '@react-three/postprocessing';
import { BlendFunction, Effect, EffectAttribute } from 'postprocessing';
import { Uniform } from 'three';

// Motion blur riding at speed: the world streaks out from where the road's heading (a zoom blur from a point a little
// above the middle of the screen), stronger toward the edges, while the bike itself, which moves with the camera, stays
// sharp: the bottom-middle of the screen, where it sits, is left out.
const fragmentShader = /* glsl */ `
uniform float amount;
uniform vec2 focus;

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  if (amount <= 0.001) {
    outputColor = inputColor;
    return;
  }
  vec2 toward = uv - focus;
  float edge = smoothstep(0.12, 0.75, length(toward * vec2(resolution.x / resolution.y, 1.0)));
  // The bike: an oval at the bottom middle.
  vec2 b = (uv - vec2(0.5, 0.0)) / vec2(0.26, 0.42);
  float bike = 1.0 - smoothstep(0.75, 1.0, length(b));
  float k = amount * edge * (1.0 - bike);
  if (k < 0.002) {
    outputColor = inputColor;
    return;
  }
  vec3 sum = inputColor.rgb;
  float jitter = fract(sin(dot(uv, vec2(12.9898, 78.233))) * 43758.5453);
  for (int i = 1; i < 10; i++) {
    float t = (float(i) + jitter) / 10.0;
    sum += texture2D(inputBuffer, uv - toward * k * 0.09 * t).rgb;
  }
  outputColor = vec4(sum / 10.0, inputColor.a);
}`;

export class SpeedBlurEffect extends Effect {
  constructor() {
    super('SpeedBlurEffect', fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      attributes: EffectAttribute.CONVOLUTION,
      uniforms: new Map<string, Uniform>([
        ['amount', new Uniform(0)],
        ['focus', new Uniform([0.5, 0.58])],
      ]),
    });
  }

  /** How strong (0 to 1, from the speed) and where it streaks out from (uv). */
  set(amount: number) {
    (this.uniforms.get('amount') as Uniform<number>).value = amount;
  }
}

export const SpeedBlur = wrapEffect(SpeedBlurEffect);
