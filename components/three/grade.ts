import { wrapEffect } from '@react-three/postprocessing';
import { BlendFunction, Effect } from 'postprocessing';
import { Uniform, Vector3 } from 'three';

// A colour grade for the landing, tuned against the reference image: a filmic shoulder, an S-curve for contrast, rose
// in the shadows and gold in the highlights. `weight` blends it in (0 everywhere else, so the hero still
// matches the blog).
const fragmentShader = /* glsl */ `
uniform float weight;
uniform float exposure;
uniform float contrast;
uniform float saturation;
uniform vec3 shadowTint;
uniform vec3 highlightTint;
uniform vec3 midTint;
uniform float glow;
uniform vec3 sunSpot;
uniform float sunAspect;

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  vec3 c = max(inputColor.rgb, vec3(0.0));
  vec3 g = c * exposure;
  // A filmic shoulder (extended Reinhard, white at 3): highlights roll off instead of clipping, so a bright sky keeps
  // its clouds and the sun its halo.
  g = g * (1.0 + g / 9.0) / (1.0 + g);
  // Contrast as an S-curve in perceptual space, so it deepens shadows without blowing highlights.
  vec3 p = pow(min(g, vec3(1.0)), vec3(1.0 / 2.2));
  p = mix(p, p * p * (3.0 - 2.0 * p), contrast - 1.0);
  g = pow(max(p, vec3(0.0)), vec3(2.2));
  float l = dot(g, vec3(0.2126, 0.7152, 0.0722));
  // Saturating past 1 can push a channel below zero, and the output's sRGB encode turns that into NaN (white).
  g = max(mix(vec3(l), g, saturation), vec3(0.0));
  // Split toning: rose in the shadows, rose-mauve through the midtones (the reference is pinker than it is yellow),
  // peach-gold in the highlights.
  vec3 tint = mix(shadowTint, midTint, smoothstep(0.02, 0.2, l));
  tint = mix(tint, highlightTint, smoothstep(0.2, 0.6, l));
  g *= tint;
  // Glow: the bright parts lift toward white, as a sunlit scene blows out on a camera (the reference has nearly four
  // times as many near-white pixels: sun, glints, lit rims, the fall).
  // It glows gold, not white: the light is saturated, as in the reference.
  g += vec3(0.5, 1.0, 0.45) * l * smoothstep(0.45, 0.9, l) * glow;
  // Vibrance: the duller colours gain the most, so greys go rosy and pale gold goes gold without the rich ones
  // clipping.
  float lv = dot(g, vec3(0.2126, 0.7152, 0.0722));
  float chroma = (max(g.r, max(g.g, g.b)) - min(g.r, min(g.g, g.b))) / max(lv, 1e-3);
  g = max(mix(vec3(lv), g, 1.0 + 0.6 * (1.0 - smoothstep(0.1, 0.8, chroma))), vec3(0.0));
  // The sun's starburst, as a camera lens draws it: thin rays of uneven length round the sun's place on screen
  // (sunSpot.xy in uv, sunSpot.z its visibility), past white so they glow.
  if (sunSpot.z > 0.0) {
    vec2 q = (uv - sunSpot.xy) * vec2(sunAspect, 1.0);
    float r = length(q);
    float ang = atan(q.y, q.x);
    // Many soft rays of uneven length (a hash per ray), fading fast: a glow with a hint of spikes, not a star.
    float n = 18.0;
    float id = floor(ang / 6.28318 * n + 0.5);
    float len = 0.015 + 0.05 * fract(sin(id * 91.3) * 437.5);
    float rays = pow(abs(cos(ang * n * 0.5)), 10.0) * exp(-r / len);
    g += vec3(1.0, 0.72, 0.42) * rays * 0.5 * sunSpot.z;
    // And the hot, saturated glow round it.
    g += vec3(1.0, 0.55, 0.25) * (exp(-r * 30.0) * 0.8 + exp(-r * 7.0) * 0.18) * sunSpot.z;
  }
  outputColor = vec4(mix(c, g, weight), inputColor.a);
}`;

const NIGHT = { shadow: new Vector3(0.95, 1.02, 0.99), mid: new Vector3(0.97, 1.02, 0.98), highlight: new Vector3(1.0, 1.02, 0.95) };
const DUSK_TONE = { shadow: new Vector3(0.98, 0.9, 1.08), mid: new Vector3(1.04, 0.97, 1.0), highlight: new Vector3(1.06, 0.98, 0.9) };

export class GradeEffect extends Effect {
  constructor() {
    super('GradeEffect', fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      uniforms: new Map<string, Uniform>([
        ['weight', new Uniform(0)],
        ['exposure', new Uniform(0.66)],
        ['contrast', new Uniform(1.5)],
        ['saturation', new Uniform(0.82)],
        ['shadowTint', new Uniform(new Vector3(0.95, 1.02, 0.99))],
        ['midTint', new Uniform(new Vector3(0.97, 1.02, 0.98))],
        ['highlightTint', new Uniform(new Vector3(1.0, 1.02, 0.95))],
        ['glow', new Uniform(0.55)],
        ['sunSpot', new Uniform(new Vector3())],
        ['sunAspect', new Uniform(1)],
      ]),
    });
  }

  set weight(value: number) {
    (this.uniforms.get('weight') as Uniform<number>).value = value;
  }

  /** The sun on screen: x, y in uv and z its visibility (0 when behind the camera or the effect is off). */
  setSun(x: number, y: number, visible: number, aspect: number) {
    (this.uniforms.get('sunSpot') as Uniform<Vector3>).value.set(x, y, visible);
    (this.uniforms.get('sunAspect') as Uniform<number>).value = aspect;
  }

  set exposure(value: number) {
    (this.uniforms.get('exposure') as Uniform<number>).value = value;
  }

  /** Blends the night's green-cold tones toward the second city's warm sunset (0 to 1). */
  setDusk(t: number) {
    const v = (name: string) => (this.uniforms.get(name) as Uniform<Vector3>).value;
    v('shadowTint').lerpVectors(NIGHT.shadow, DUSK_TONE.shadow, t);
    v('midTint').lerpVectors(NIGHT.mid, DUSK_TONE.mid, t);
    v('highlightTint').lerpVectors(NIGHT.highlight, DUSK_TONE.highlight, t);
    (this.uniforms.get('saturation') as Uniform<number>).value = 0.82 + (1.2 - 0.82) * t;
  }

  set glow(value: number) {
    (this.uniforms.get('glow') as Uniform<number>).value = value;
  }
}

export const Grade = wrapEffect(GradeEffect);
