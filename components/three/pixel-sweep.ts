import { wrapEffect } from '@react-three/postprocessing';
import { BlendFunction, Effect, EffectAttribute } from 'postprocessing';
import { Uniform } from 'three';

// The hand-over from the crisp hero to pixel mode: a wipe of pixelation running diagonally up the screen as you
// scroll through the pre-roll (lib/journey.ts PRE_ROLL). Ahead of the wipe the full-resolution render shows through;
// behind it each cell takes one colour, the same cells the low-resolution render then draws once the wipe's done
// (components/three/journey-canvas.tsx), so the switch to it can't be seen. The wipe's edge steps cell by cell, ragged.
const fragmentShader = /* glsl */ `
uniform float progress;
uniform float cell;

float cellHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  if (progress <= 0.0) {
    outputColor = inputColor;
    return;
  }
  vec2 px = uv * resolution;
  vec2 id = floor(px / cell);
  vec2 centre = (id + 0.5) * cell / resolution;
  // Along the diagonal, bottom-left (0) to top-right (1), measured at the cell, jittered so the edge is ragged.
  float along = (centre.x + centre.y) * 0.5;
  float jitter = (cellHash(id) - 0.5) * 0.12;
  float edge = progress * 1.3 - 0.15 + jitter;
  if (along >= edge) {
    outputColor = inputColor;
    return;
  }
  vec3 c = texture2D(inputBuffer, centre).rgb;
  // A band of glowing colour riding the wave's front, so the change is unmistakable: gold-white at the leading edge,
  // through rose to violet, cells flickering in and out of it.
  float behind = (edge - along) / 0.12;
  if (behind < 1.0 && progress < 1.0) {
    vec3 band = behind < 0.3 ? mix(vec3(1.0, 0.78, 0.32), vec3(0.98, 0.3, 0.55), behind / 0.3)
                             : mix(vec3(0.98, 0.3, 0.55), vec3(0.45, 0.3, 0.92), (behind - 0.3) / 0.7);
    float flicker = step(0.25, fract(cellHash(id + floor(time * 14.0)) + behind * 0.5));
    float strength = (1.0 - smoothstep(0.5, 1.0, behind)) * mix(0.6, 1.0, flicker);
    c = mix(c, band * (0.9 + 0.4 * (1.0 - behind)), strength * 0.95);
  }
  outputColor = vec4(c, inputColor.a);
}`;

export class PixelSweepEffect extends Effect {
  constructor() {
    super('PixelSweepEffect', fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      attributes: EffectAttribute.CONVOLUTION,
      uniforms: new Map<string, Uniform>([
        ['progress', new Uniform(0)],
        ['cell', new Uniform(4)],
      ]),
    });
  }

  /** Wipe progress (0 to 1) and cell size in buffer pixels. */
  set(progress: number, cell: number) {
    (this.uniforms.get('progress') as Uniform<number>).value = progress;
    (this.uniforms.get('cell') as Uniform<number>).value = cell;
  }
}

export const PixelSweep = wrapEffect(PixelSweepEffect);
