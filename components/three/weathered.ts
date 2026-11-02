import type { Material, MeshStandardMaterial } from 'three';

// Weathering for the barriers and rails the bike passes up close, drawn from world position (so it works on instances
// and any size of box, and stays put as the street recycles): concrete gets form-panel seams, grit, grime streaking down
// from the top and a dark wet foot; steel gets brushed lines along it and blotches of rust. Colour and roughness only.

const NOISE = /* glsl */ `
float weatherHash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float weatherNoise(vec2 p) {
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(weatherHash(i), weatherHash(i + vec2(1, 0)), u.x), mix(weatherHash(i + vec2(0, 1)), weatherHash(i + vec2(1, 1)), u.x), u.y);
}`;

const CONCRETE = /* glsl */ `
{
  // Along the wall (horizontal, in its own direction) and up it.
  vec2 t = abs(wn.y) > 0.5 ? vec2(0.7071) : normalize(vec2(-wn.z, wn.x));
  float along = dot(wp.xz, t);
  float grit = weatherNoise(vec2(along, wp.y) * 9.0) * 0.6 + weatherNoise(vec2(along, wp.y) * 37.0) * 0.4;
  // Grime streaking down from the top edge, in uneven runs.
  float runs = weatherNoise(vec2(along * 2.3, 0.0)) * 0.7 + weatherNoise(vec2(along * 9.0, wp.y * 0.6)) * 0.3;
  float streak = smoothstep(0.35, 0.9, runs) * smoothstep(-11.0, -9.8, wp.y);
  // Form-panel seams every 4 m.
  float seam = 1.0 - smoothstep(0.0, 0.04, abs(fract(along / 4.0 + 0.5) - 0.5) * 4.0);
  // Wet at the foot, where the rain runs off the road.
  float wet = 1.0 - smoothstep(-11.0, -10.55, wp.y);
  // (Strong, since it's mostly seen by night: the variation is what reads.)
  float blotch = weatherNoise(vec2(along, wp.y) * 1.3);
  diffuseColor.rgb *= (0.55 + 0.95 * grit) * (0.75 + 0.6 * blotch) * (1.0 - 0.6 * streak) * (1.0 - 0.7 * seam) * (1.0 - 0.5 * wet);
  weatherRough = mix(0.92, 0.35, wet) - 0.1 * streak;
}`;

const STEEL = /* glsl */ `
{
  vec2 t = abs(wn.y) > 0.5 ? vec2(0.7071) : normalize(vec2(-wn.z, wn.x));
  float along = dot(wp.xz, t);
  // Brushed along its length.
  float brushed = weatherNoise(vec2(along * 0.4, wp.y * 160.0));
  // Rust in blotches, worst toward the bottom edge.
  float rust = smoothstep(0.55, 0.8, weatherNoise(vec2(along, wp.y * 3.0) * 1.7) * 0.7 + weatherNoise(vec2(along, wp.y) * 11.0) * 0.3);
  diffuseColor.rgb = mix(diffuseColor.rgb * (0.85 + 0.3 * brushed), vec3(0.16, 0.07, 0.035), rust * 0.85);
  weatherRough = mix(0.32 + 0.15 * brushed, 0.9, rust);
  weatherMetal = mix(1.0, 0.2, rust);
}`;

export type Weathering = 'concrete' | 'steel';

export function weathered<T extends MeshStandardMaterial>(material: T, kind: Weathering): T {
  // (Once per material: a model's materials are shared and its setup can run again, e.g. on a hot reload.)
  if (material.userData.weathered) return material;
  material.userData.weathered = kind;
  const previous = material.onBeforeCompile;
  material.onBeforeCompile = (shader, renderer) => {
    previous?.call(material, shader, renderer);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vWeatherWorld;\nvarying vec3 vWeatherNormal;')
      .replace(
        '#include <project_vertex>',
        `#include <project_vertex>
mat4 weatherModel = modelMatrix;
#ifdef USE_INSTANCING
weatherModel = modelMatrix * instanceMatrix;
#endif
vWeatherWorld = (weatherModel * vec4(transformed, 1.0)).xyz;
vWeatherNormal = mat3(weatherModel) * objectNormal;`
      );
    shader.fragmentShader = shader.fragmentShader
      .replace('#include <common>', `#include <common>\nvarying vec3 vWeatherWorld;\nvarying vec3 vWeatherNormal;\n${NOISE}`)
      .replace(
        '#include <color_fragment>',
        `#include <color_fragment>
vec3 wp = vWeatherWorld;
vec3 wn = normalize(vWeatherNormal);
float weatherRough = -1.0;
float weatherMetal = -1.0;
${kind === 'concrete' ? CONCRETE : STEEL}`
      )
      .replace('#include <roughnessmap_fragment>', '#include <roughnessmap_fragment>\nif (weatherRough >= 0.0) roughnessFactor = weatherRough;')
      .replace('#include <metalnessmap_fragment>', '#include <metalnessmap_fragment>\nif (weatherMetal >= 0.0) metalnessFactor *= weatherMetal;');
  };
  const key = material.customProgramCacheKey.bind(material);
  material.customProgramCacheKey = () => `${key()}-weathered-${kind}`;
  return material;
}

export const isWeatherable = (m: Material) => (m as MeshStandardMaterial).isMeshStandardMaterial === true;
