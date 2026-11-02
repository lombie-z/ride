import type { MeshStandardMaterial } from 'three';
import { scan, TRIPLANAR } from './scans';

// Detail for the landing's canyon (art/build-landing.py): a scanned rock surface (Poly Haven's layered cliff_side
// sandstone) projected onto the walls from three sides and stretched into tall fractures, its detail and relief kept
// but recoloured to the reference's pink-cream; colour drifting through peach, rose and cream;
// crisp facets on the blocks; moss creeping onto the ledges. The mesh's vertex colour stays the base.
const NOISE = /* glsl */ `
float rHash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float rNoise(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  vec3 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(rHash(i), rHash(i + vec3(1, 0, 0)), u.x), mix(rHash(i + vec3(0, 1, 0)), rHash(i + vec3(1, 1, 0)), u.x), u.y),
    mix(mix(rHash(i + vec3(0, 0, 1)), rHash(i + vec3(1, 0, 1)), u.x), mix(rHash(i + vec3(0, 1, 1)), rHash(i + vec3(1, 1, 1)), u.x), u.y),
    u.z);
}
float rFbm(vec3 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 4; i++) { v += a * rNoise(p); p = p * 2.1 + 3.7; a *= 0.5; }
  return v;
}
`;

// Where on the wall, and how the three projections weigh in.
const PROJECTION = /* glsl */ `
  vec3 nW = normalize(vRockNormal);
  vec3 w = triWeights(nW);
  // Stretched up the walls, so its cracks run as tall vertical fractures.
  vec3 pc = vRockPos * vec3(1.0 / 9.0, 1.0 / 16.0, 1.0 / 9.0);
`;

export function rockMaterial(source: MeshStandardMaterial) {
  const material = source.clone();
  material.roughness = 0.9;
  const cliff = scan('cliff_side');
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, {
      uCliffDiff: { value: cliff.diff },
      uCliffNor: { value: cliff.nor },
      uCliffRough: { value: cliff.rough },
      uCliffMean: { value: cliff.mean },
    });
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vRockPos;\nvarying vec3 vRockNormal;')
      .replace(
        '#include <begin_vertex>',
        '#include <begin_vertex>\nvRockPos = (modelMatrix * vec4(transformed, 1.0)).xyz;\nvRockNormal = normalize(mat3(modelMatrix) * objectNormal);'
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
varying vec3 vRockPos;
varying vec3 vRockNormal;
uniform sampler2D uCliffDiff, uCliffNor, uCliffRough;
uniform vec3 uCliffMean;
${NOISE}
${TRIPLANAR}`
      )
      .replace(
        '#include <color_fragment>',
        `#include <color_fragment>
{
  vec3 p = vRockPos;
  float steep = 1.0 - abs(vRockNormal.y);
  ${PROJECTION}
  // The scans' detail, relative to their own average colour: mostly light and shade, a little of their hue.
  vec3 detail = tri(uCliffDiff, pc, w) / uCliffMean;
  detail = mix(vec3(dot(detail, vec3(0.2126, 0.7152, 0.0722))), detail, 0.25);
  // Pushed past the scans' own contrast, so crevices go deep (an ambient-occlusion stand-in) and lit faces stay pale.
  detail = pow(clamp(detail, 0.0, 2.5), vec3(1.6));
  diffuseColor.rgb *= clamp(detail, 0.0, 2.2);
  // Colour drift through peach, rose and cream, darker down in the fractures.
  float hue = rFbm(p * 0.35 + 7.0);
  // Pinker and creamier than the base, less orange (as the reference's rock).
  vec3 tint = mix(vec3(1.02, 0.88, 0.92), vec3(1.06, 0.98, 0.92), smoothstep(0.35, 0.65, hue));
  tint = mix(tint, vec3(0.94, 0.8, 0.9), smoothstep(0.55, 0.8, rFbm(p * 1.1 + 2.0)) * 0.6);
  diffuseColor.rgb *= tint;
  // Paler and less orange than the vertex colours: the reference's rock is a sunlit pink-cream.
  float luma = dot(diffuseColor.rgb, vec3(0.299, 0.587, 0.114));
  diffuseColor.rgb = mix(vec3(luma), diffuseColor.rgb, 0.62) * vec3(1.08, 1.0, 1.02) + 0.04;
  // Moss and small plants on ledges and the gentler slopes, in patches, and hanging down the faces in streaks.
  float ledge = smoothstep(0.55, 0.85, vRockNormal.y) * smoothstep(0.35, 0.6, rFbm(p * 1.6 + 11.0));
  float hanging = steep * smoothstep(0.58, 0.72, rFbm(vec3(p.x * 0.9, p.y * 0.35, p.z * 0.9) + 31.0));
  ledge = max(ledge, hanging * 0.9);
  vec3 moss = mix(vec3(0.2, 0.32, 0.12), vec3(0.42, 0.5, 0.2), rNoise(p * 6.0));
  diffuseColor.rgb = mix(diffuseColor.rgb, moss, ledge * 0.85 * step(-10.7, p.y));
}`
      )
      .replace(
        '#include <roughnessmap_fragment>',
        `#include <roughnessmap_fragment>
{
  ${PROJECTION}
  roughnessFactor = clamp(tri(uCliffRough, pc, w).r, 0.55, 1.0);
}`
      )
      .replace(
        '#include <normal_fragment_maps>',
        `#include <normal_fragment_maps>
{
  ${PROJECTION}
  // Crisp facets first (lean toward each face's true, flat normal, so the blocks read as planes with edges), then the
  // scans' relief on top.
  vec3 facet = normalize(cross(dFdx(vRockPos), dFdy(vRockPos)));
  if (dot(facet, nW) < 0.0) facet = -facet;
  vec3 base = normalize(mix(nW, facet, 0.5 * (1.0 - abs(nW.y))));
  vec3 relief = triNormal(uCliffNor, pc, w, base, 2.2);
  normal = normalize((viewMatrix * vec4(relief, 0.0)).xyz);
}`
      );
  };
  material.customProgramCacheKey = () => 'canyon-rock-scanned';
  return material;
}
