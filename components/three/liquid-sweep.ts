import { wrapEffect } from '@react-three/postprocessing';
import { BlendFunction, Effect, EffectAttribute } from 'postprocessing';
import { Uniform } from 'three';

// Getting off after a ride: a sheet of liquid glass washes across the screen from the right (components/three/ride.tsx
// lib/ride.ts ride.wash), and while it covers everything the ride is put back, the bike at its spot and the camera at
// the landing; then it drains away to the left. Behind its front the picture is seen through moving water: refracted,
// split at the edges into colour, darkened a little, with a bright meniscus riding the front.
const fragmentShader = /* glsl */ `
uniform float cover;
uniform float leaving;

float liquidHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float liquidNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(liquidHash(i), liquidHash(i + vec2(1, 0)), u.x), mix(liquidHash(i + vec2(0, 1)), liquidHash(i + vec2(1, 1)), u.x), u.y);
}
// Moving water's surface height: slow swells and quicker ripples, stretched along the sheet's travel.
float surface(vec2 p) {
  return liquidNoise(p * vec2(2.2, 3.4) + vec2(time * 0.6, time * 0.2)) * 0.75 + liquidNoise(p * vec2(5.5, 8.0) - vec2(time * 1.4, 0.0)) * 0.25;
}

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  if (cover <= 0.0) {
    outputColor = inputColor;
    return;
  }
  float aspect = resolution.x / resolution.y;
  vec2 p = vec2(uv.x * aspect, uv.y);
  // The front: coming in from the right as cover rises, going out to the left as it falls (leaving), wobbling.
  float wobble = (liquidNoise(vec2(uv.y * 4.0, time * 1.3)) - 0.5) * 0.12 + sin(uv.y * 9.0 + time * 3.0) * 0.015;
  float x = leaving > 0.5 ? 1.0 - uv.x : uv.x;
  float edge = 1.0 - cover * 1.25 + wobble;
  float inside = smoothstep(edge - 0.004, edge + 0.004, x);
  if (inside <= 0.0) {
    outputColor = inputColor;
    return;
  }
  // Refraction through the surface: its slope bends the view, strongest just behind the front where it's deepest.
  float e = 0.01;
  float h = surface(p);
  vec2 slope = vec2(surface(p + vec2(e, 0.0)) - h, surface(p + vec2(0.0, e)) - h) / e;
  float depth = smoothstep(0.0, 0.18, x - edge);
  vec2 bend = slope * 0.0045 * (0.4 + 0.6 * depth) + vec2(0.0, -0.006) * depth;
  // Colour splits at the bends: red bent less, blue more.
  vec3 c;
  c.r = texture2D(inputBuffer, uv + bend * 0.8).r;
  c.g = texture2D(inputBuffer, uv + bend).g;
  c.b = texture2D(inputBuffer, uv + bend * 1.25).b;
  // A cool tint and a glassy sheen where the surface faces up the screen.
  c = c * vec3(0.82, 0.95, 0.9) + vec3(0.35, 0.6, 0.45) * pow(max(0.0, slope.y * 0.12 + 0.2), 3.0);
  // The meniscus: a bright rim of light on the front.
  float rim = exp(-abs(x - edge) * 140.0) + 0.4 * exp(-abs(x - edge - 0.02) * 40.0);
  c += vec3(0.75, 1.0, 0.8) * rim * 0.9;
  outputColor = vec4(mix(inputColor.rgb, c, inside), inputColor.a);
}`;

export class LiquidSweepEffect extends Effect {
  constructor() {
    super('LiquidSweepEffect', fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      attributes: EffectAttribute.CONVOLUTION,
      uniforms: new Map<string, Uniform>([
        ['cover', new Uniform(0)],
        ['leaving', new Uniform(0)],
      ]),
    });
  }

  /** How much of the screen the sheet covers (0 to 1), and whether it's draining away (to the left) rather than coming in. */
  set(cover: number, leaving: boolean) {
    (this.uniforms.get('cover') as Uniform<number>).value = cover;
    (this.uniforms.get('leaving') as Uniform<number>).value = leaving ? 1 : 0;
  }
}

export const LiquidSweep = wrapEffect(LiquidSweepEffect);
