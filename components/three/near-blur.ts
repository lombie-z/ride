import { wrapEffect } from '@react-three/postprocessing';
import { BlendFunction, Effect, EffectAttribute } from 'postprocessing';
import { Uniform } from 'three';

// The reference's shallow focus: the frame's foot (the near water, pads and pebbles, all lying below the frog in the
// frame at the landing's eye-level view) melts into soft discs, glints into bokeh, while the frog and everything
// beyond stay sharp. At the landing the camera holds still and the ground plane rises up the frame with distance, so
// height in the frame stands in for depth. (A full depth of field also blurred the distant fall and cliffs, which the
// reference keeps crisp.) `weight` fades it in at the landing.
const fragmentShader = /* glsl */ `
uniform float weight;
uniform float sharpAbove;
uniform float softBelow;
uniform float maxRadius;

float nearness(vec2 at) {
  return 1.0 - smoothstep(softBelow, sharpAbove, at.y);
}

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  float amount = nearness(uv) * weight;
  if (amount < 0.01) {
    outputColor = inputColor;
    return;
  }
  // A golden-angle disc of taps; taps on sharper ground count less, so the blur doesn't smear the sharp frame in.
  vec2 radius = maxRadius * amount * texelSize;
  vec4 sum = vec4(inputColor.rgb, 1.0);
  for (int i = 1; i < 32; i++) {
    float r = sqrt(float(i) / 32.0);
    float a = float(i) * 2.39996;
    vec2 at = uv + vec2(cos(a), sin(a)) * r * radius;
    float w = 0.25 + 0.75 * nearness(at);
    sum += vec4(texture2D(inputBuffer, at).rgb * w, w);
  }
  outputColor = vec4(sum.rgb / sum.a, inputColor.a);
}`;

export class NearBlurEffect extends Effect {
  constructor() {
    super('NearBlurEffect', fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      attributes: EffectAttribute.CONVOLUTION,
      uniforms: new Map<string, Uniform>([
        ['weight', new Uniform(0)],
        // Frame heights (0 at the foot): sharp from just under the frog's pad, fully soft along the bottom edge.
        ['sharpAbove', new Uniform(0.2)],
        ['softBelow', new Uniform(0.03)],
        ['maxRadius', new Uniform(14)],
      ]),
    });
  }

  set radius(value: number) {
    (this.uniforms.get('maxRadius') as Uniform<number>).value = value;
  }

  set weight(value: number) {
    (this.uniforms.get('weight') as Uniform<number>).value = value;
  }
}

export const NearBlur = wrapEffect(NearBlurEffect);
