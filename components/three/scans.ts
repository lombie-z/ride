import { RepeatWrapping, SRGBColorSpace, type Texture, TextureLoader, Vector3 } from 'three';

// Scanned surfaces from Poly Haven (CC0, polyhaven.com), in public/textures/landing: colour, OpenGL normal and
// roughness maps for each. The landing's shaders project them from three sides (triplanar), since the canyon and the
// stones have no UVs.

export type Scan = { diff: Texture; nor: Texture; rough: Texture; mean: Vector3 };

// Mean linear colour of each colour map, so a shader can use a scan's detail while keeping its own palette.
const MEANS: Record<string, [number, number, number]> = {
  cliff_side: [0.211, 0.091, 0.033],
  rock_boulder_dry: [0.398, 0.337, 0.271],
};

const loader = new TextureLoader();
const cache = new Map<string, Scan>();

function load(url: string, colour: boolean) {
  const texture = loader.load(url);
  texture.wrapS = texture.wrapT = RepeatWrapping;
  texture.anisotropy = 8;
  if (colour) texture.colorSpace = SRGBColorSpace;
  return texture;
}

export function scan(name: keyof typeof MEANS): Scan {
  let s = cache.get(name);
  if (!s) {
    const base = `/textures/landing/${name}`;
    s = {
      diff: load(`${base}_diff.jpg`, true),
      nor: load(`${base}_nor.jpg`, false),
      rough: load(`${base}_rough.jpg`, false),
      mean: new Vector3(...MEANS[name]),
    };
    cache.set(name, s);
  }
  return s;
}

/**
 * GLSL for triplanar sampling: `tri(map, p, w)` samples a map projected along each world axis, blended by the weights
 * `w`; `triNormal(map, p, w, n, strength)` does the same for a tangent-space normal map (whiteout blend), returning a
 * world-space normal.
 */
export const TRIPLANAR = /* glsl */ `
vec3 triWeights(vec3 n) {
  vec3 w = pow(abs(n), vec3(4.0));
  return w / (w.x + w.y + w.z);
}
vec3 tri(sampler2D map, vec3 p, vec3 w) {
  return texture2D(map, p.zy).rgb * w.x + texture2D(map, p.xz).rgb * w.y + texture2D(map, p.xy).rgb * w.z;
}
vec3 triNormal(sampler2D map, vec3 p, vec3 w, vec3 n, float strength) {
  vec3 tx = texture2D(map, p.zy).xyz * 2.0 - 1.0;
  vec3 ty = texture2D(map, p.xz).xyz * 2.0 - 1.0;
  vec3 tz = texture2D(map, p.xy).xyz * 2.0 - 1.0;
  tx.xy *= strength; ty.xy *= strength; tz.xy *= strength;
  tx = vec3(tx.xy + n.zy, abs(tx.z) * n.x);
  ty = vec3(ty.xy + n.xz, abs(ty.z) * n.y);
  tz = vec3(tz.xy + n.xy, abs(tz.z) * n.z);
  return normalize(tx.zyx * w.x + ty.xzy * w.y + tz.xyz * w.z);
}
`;
