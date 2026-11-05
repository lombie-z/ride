import {
  type Camera,
  Color,
  FramebufferTexture,
  HalfFloatType,
  LinearFilter,
  LinearMipmapLinearFilter,
  Matrix4,
  type Mesh,
  NoBlending,
  NoColorSpace,
  type Object3D,
  RepeatWrapping,
  ShaderMaterial,
  type Texture,
  TextureLoader,
  UniformsLib,
  UniformsUtils,
  UnsignedByteType,
  Vector2,
  Vector3,
  type WebGLRenderer,
} from 'three';

// The flooded tunnel's water: black, with the tube's lamps and the bulkhead's red lying in it. It's the frame's biggest surface, so no second
// render of a 480k triangle tunnel for it. Instead: drawn first among the see-through things, it takes a copy of what's been drawn so far
// (at the scene's pixel size, 7, that's a few hundred pixels across), and for each of its pixels works out where its reflected ray
// meets the tube and looks up that spot in the copy. Anything off screen isn't in it; rough water hides that.

const vertexShader = /* glsl */ `
varying vec3 vWorld;
#include <fog_pars_vertex>
void main() {
  vec4 world = modelMatrix * vec4(position, 1.0);
  vWorld = world.xyz;
  vec4 mvPosition = viewMatrix * world;
  gl_Position = projectionMatrix * mvPosition;
  #include <fog_vertex>
}`;

const fragmentShader = /* glsl */ `
uniform sampler2D uNormal;
uniform sampler2D uScene;
uniform mat4 uProjection;
uniform float uTime;
uniform vec3 uDeep;
uniform vec3 uGlint;
uniform vec3 uAxis;
uniform vec3 uEye;
uniform float uCentre;
uniform float uRadius;
uniform float uEnd;
uniform float uStrength;
uniform float uDoor;
uniform float uRed;
varying vec3 vWorld;
#include <fog_pars_fragment>

/** Where the ray from P along R meets the tube round the view's axis, or the plane of its end. */
vec3 hit(vec3 P, vec3 R) {
  vec3 side = vec3(-uAxis.z, 0.0, uAxis.x);
  float a = dot(P - uEye, side);
  float h = P.y - uCentre;
  float ra = dot(R, side);
  float rh = R.y;
  float A = ra * ra + rh * rh;
  float B = a * ra + h * rh;
  float C = a * a + h * h - uRadius * uRadius;
  float t = (-B + sqrt(max(B * B - A * C, 0.0))) / max(A, 1e-3);
  float along = dot(P - uEye, uAxis);
  float toward = dot(R, uAxis);
  if (toward > 1e-3) t = min(t, max(uEnd - along, 0.0) / toward);
  return P + R * t;
}

vec3 lookUp(vec3 Q) {
  vec4 clip = uProjection * viewMatrix * vec4(Q, 1.0);
  vec2 uv = clip.xy / max(clip.w, 1e-3) * 0.5 + 0.5;
  // (Off the top of the frame, it's gone; off its sides the edge smears in, as rough water would.)
  float seen = smoothstep(1.06, 0.9, uv.y) * smoothstep(1.2, 0.98, abs(uv.x - 0.5) * 2.0);
  return texture2D(uScene, clamp(uv, 0.002, 0.998)).rgb * seen;
}

void main() {
  vec2 p = vWorld.xz;
  // Two copies of the ripples, drifting apart; finer ones flatten off into the distance with the map's mips.
  vec3 n1 = texture2D(uNormal, p / 9.0 + vec2(uTime * 0.021, uTime * 0.013)).xyz * 2.0 - 1.0;
  vec3 n2 = texture2D(uNormal, p / 3.3 - vec2(uTime * 0.034, -uTime * 0.027)).xyz * 2.0 - 1.0;
  vec2 ripple = n1.xy * 0.62 + n2.xy * 0.38;
  vec3 N = normalize(vec3(ripple.x * 0.2, 1.0, ripple.y * 0.2));
  vec3 V = normalize(cameraPosition - vWorld);
  float facing = max(dot(V, N), 0.0);
  float fresnel = 0.03 + 0.97 * pow(1.0 - facing, 4.5);

  // Three looks along the rippled ray, the further ones rougher: long streaks of light down the water.
  vec3 R0 = reflect(-V, N);
  R0.y = max(R0.y, 0.015);
  vec3 N1 = normalize(vec3(ripple.x * 0.34, 1.0, ripple.y * 0.34));
  vec3 R1 = reflect(-V, N1);
  R1.y = max(R1.y, 0.015);
  vec3 N2 = normalize(vec3(ripple.x * 0.1, 1.0, ripple.y * 0.1));
  vec3 R2 = reflect(-V, N2);
  R2.y = max(R2.y, 0.015);
  vec3 reflection = lookUp(hit(vWorld, R0)) * 0.5 + lookUp(hit(vWorld, R1)) * 0.28 + lookUp(hit(vWorld, R2)) * 0.34;
  // Black: the tube's walls leave it dark, only what's lit shows. 
  float lit = dot(reflection, vec3(0.3, 0.6, 0.1));
  reflection = min(reflection * smoothstep(0.02, 0.2, lit), vec3(3.0));

  vec3 col = uDeep + reflection * fresnel * uStrength;
  // Sharp glints where a crest catches the light: the tube's far lamps to either side, and straight ahead (red as the door nears).
  vec2 fine = n2.xy * 0.8 + n1.xy * 0.2;
  vec3 Nc = normalize(vec3(fine.x * 0.42, 1.0, fine.y * 0.42));
  vec3 across = vec3(-uAxis.z, 0.0, uAxis.x);
  vec3 L = uAxis + vec3(0.0, 0.42, 0.0);
  float ahead = pow(max(dot(Nc, normalize(V + normalize(L))), 0.0), 640.0);
  float left = pow(max(dot(Nc, normalize(V + normalize(L - across * 0.62))), 0.0), 640.0);
  float right = pow(max(dot(Nc, normalize(V + normalize(L + across * 0.62))), 0.0), 640.0);
  // (Not close under the bike: there, the ripples' shapes are many pixels across.)
  float far = smoothstep(4.0, 16.0, length(vWorld - cameraPosition));
  col += far * (mix(uGlint, vec3(0.9, 0.06, 0.02), min(uRed, 1.0)) * ahead + vec3(0.05, 0.36, 0.12) * (left + right));
  // The door's red on the water, laid down its middle towards the bike, broken up by the ripples.
  if (uRed > 0.0) {
    float side = dot(vWorld - uEye, across);
    float back = uDoor - dot(vWorld - uEye, uAxis);
    float column = exp(-side * side / (5.0 + back * 0.1)) * exp(-max(back, 0.0) / 20.0) * step(0.0, back);
    col += vec3(0.9, 0.05, 0.02) * uRed * column * far * smoothstep(0.0, 0.4, fine.y + fine.x * 0.4);
  }
  gl_FragColor = vec4(col, 1.0);
  #include <fog_fragment>
  #include <colorspace_fragment>
}`;

const projection = new Matrix4();

/** The water's material, and what has to be kept up each frame. One, for however many pieces of water there are. */
export function makeWater(gl: WebGLRenderer) {
  const normal = new TextureLoader().load('/textures/fx/water-normal.png', (t) => gl.initTexture(t));
  normal.colorSpace = NoColorSpace;
  normal.wrapS = normal.wrapT = RepeatWrapping;
  normal.minFilter = LinearMipmapLinearFilter;
  normal.magFilter = LinearFilter;
  normal.anisotropy = 2;

  let copy: FramebufferTexture | null = null;
  let copied = -1;
  const size = new Vector2();
  const viewer = { camera: null as Camera | null };

  const material = new ShaderMaterial({
    vertexShader,
    fragmentShader,
    uniforms: UniformsUtils.merge([
      UniformsLib.fog,
      {
        uTime: { value: 0 },
        uDeep: { value: new Color(0.004, 0.0065, 0.0055) },
        uGlint: { value: new Color(0.42, 0.5, 0.45) },
        uCentre: { value: 0 },
        uRadius: { value: 9 },
        uEnd: { value: 1e4 },
        uStrength: { value: 1.25 },
        uDoor: { value: 1e4 },
        uRed: { value: 0 },
      },
    ]),
    fog: true,
    // (See-through, to be drawn after everything solid, though it isn't: it's what's in the copy.)
    transparent: true,
    blending: NoBlending,
    depthWrite: true,
  });
  material.name = 'SectionWater';
  material.uniforms.uNormal = { value: normal };
  material.uniforms.uScene = { value: null as Texture | null };
  material.uniforms.uProjection = { value: projection };
  material.uniforms.uAxis = { value: new Vector3(1, 0, 0) };
  material.uniforms.uEye = { value: new Vector3() };

  material.onBeforeRender = (renderer: WebGLRenderer, _scene, camera: Camera) => {
    const frame = renderer.info.render.frame;
    // (Not for anyone's reflection, nor a second piece of water in the same frame.)
    if (copied === frame || camera !== viewer.camera) return;
    const target = renderer.getRenderTarget();
    const type = target ? target.texture.type : UnsignedByteType;
    if (target) size.set(target.width, target.height);
    else renderer.getDrawingBufferSize(size);
    if (!copy || copy.image.width !== size.x || copy.image.height !== size.y || copy.type !== type) {
      copy?.dispose();
      copy = new FramebufferTexture(size.x, size.y);
      copy.type = type === HalfFloatType ? HalfFloatType : UnsignedByteType;
      copy.minFilter = copy.magFilter = LinearFilter;
      copy.generateMipmaps = false;
    }
    renderer.copyFramebufferToTexture(copy);
    material.uniforms.uScene.value = copy;
    material.uniformsNeedUpdate = true;
    copied = frame;
    projection.copy(camera.projectionMatrix);
  };

  const seen = new WeakSet<Mesh>();
  const dress = (o: Object3D) => {
    const mesh = o as Mesh;
    if (!mesh.isMesh || seen.has(mesh)) return;
    seen.add(mesh);
    const m = mesh.material;
    if (!Array.isArray(m) && m.name === 'City5Water') {
      mesh.material = material;
      // (First among the see-through things: whatever's behind the bike's screen, and the spray, on top of it.)
      mesh.renderOrder = -2;
    }
  };

  return {
    material,
    /** The camera whose frame it's in. */
    viewer,
    /** The glbs' water, by its name, wherever it's been put (components/three/zone-city.tsx and on). */
    dress,
    dispose() {
      copy?.dispose();
      normal.dispose();
      material.dispose();
    },
  };
}
