'use client';

import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import {
  BackSide,
  Color,
  type DirectionalLight,
  Fog,
  type Mesh,
  RepeatWrapping,
  ShaderMaterial,
  SRGBColorSpace,
  type Texture,
  TextureLoader,
  Vector3,
} from 'three';
import { BEATS, devFlag, journey, smoothstep } from '@/lib/journey';
import { ride } from '@/lib/ride';

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

// Above the clouds everything sits on the blog's plaster; below them it's night over the green city: a low overcast
// lit from beneath by the city's glow.
export const PLASTER = new Color('#f5f2ed');
const SKY_TOP = new Color('#141b17');
const SKY_HORIZON = new Color('#3e4c44');
// The haze on the way down and over the city: green-grey smog.
const DESCENT_HAZE = new Color('#2a3530');
// No sun: a moon behind the overcast, up to the right of the city, silvering the cloud round it.
const SUN_GLOW = new Color('#3c4a42');
const MOON = new Vector3(1, 0.5, 0.75).normalize();
const CLOUD_LIT = new Color('#7a8c81');
const CLOUD_SHADE = new Color('#1c2520');
// The night's key: cold light from high on the left, behind the camera, so the bike's chrome and carapace catch it and
// its glare off the wet road falls away from the camera rather than whiting the road out.
const WARM_LIGHT = new Color('#cfe8d4');
/** Where the sun sits (art/build-sky.py), in three.js space (y up). */
export const SUN_POSITION = new Vector3(47.6, 7.4, -47.4);
const LANDING_LIGHT = new Vector3(-63.81, 14, 31.48);

/** 0 above the clouds, 1 once the sun is fully out. */
export const bloomAt = (frame: number) => smoothstep(BEATS.sunIn, BEATS.sunFull, frame);

const vertexShader = /* glsl */ `
varying vec3 vDirection;
void main() {
  vDirection = normalize((modelMatrix * vec4(position, 0.0)).xyz);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}`;

const fragmentShader = /* glsl */ `
uniform vec3 uTop;
uniform vec3 uHorizon;
uniform vec3 uGlow;
uniform vec3 uCloudLit;
uniform vec3 uCloudShade;
uniform vec3 uSun;
uniform float uOpacity;
uniform float uTime;
uniform float uDebug;
uniform sampler2D uPhotoSky;
uniform float uPhoto;
varying vec3 vDirection;
float hash3(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }
float vnoise3(vec3 p) {
  vec3 i = floor(p), f = fract(p);
  vec3 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(mix(hash3(i), hash3(i + vec3(1, 0, 0)), u.x), mix(hash3(i + vec3(0, 1, 0)), hash3(i + vec3(1, 1, 0)), u.x), u.y),
    mix(mix(hash3(i + vec3(0, 0, 1)), hash3(i + vec3(1, 0, 1)), u.x), mix(hash3(i + vec3(0, 1, 1)), hash3(i + vec3(1, 1, 1)), u.x), u.y),
    u.z);
}
float fbm3(vec3 p) {
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 5; i++) { v += a * vnoise3(p); p = p * 2.07 + 5.3; a *= 0.5; }
  return v;
}
// Clouds on a layer overhead, seen in perspective (shrinking and crowding toward the horizon, as real cloud fields do):
// p is where the view ray meets the layer.
vec2 cloudPlane(vec3 d) { return d.xz / (max(d.y, 0.0) + 0.22) * 1.6 + vec2(uTime * 0.012, 0.0); }
float clouds(vec2 q) {
  // Domain-warped so they billow into heaps rather than streak.
  vec3 p = vec3(q, 0.0);
  p.xy += vec2(fbm3(p * 0.5 + 9.0), fbm3(p * 0.5 + 17.0)) * 0.45;
  float base = fbm3(p * 1.5);
  // Cauliflower detail on the edges: small heaps where the cloud is thin.
  return base + (fbm3(p * 6.0 + 3.0) - 0.5) * 0.16 * (1.0 - smoothstep(0.5, 0.65, base));
}
void main() {
  vec3 d = normalize(vDirection);
  vec3 sky = mix(uHorizon, uTop, smoothstep(-0.02, 0.32, d.y));
  float toward = max(dot(d, uSun), 0.0);
  // The moon behind the overcast: only a soft, wide glow (no disc, no starburst).
  sky += uGlow * (pow(toward, 6.0) * 0.45 + pow(toward, 40.0) * 0.6);
  // Heaped clouds over half the sky: mauve-rose cores, gold where they face the low sun (the layer's density a step
  // toward the sun is lower there), bright silver linings near it; thinning into the horizon haze.
  vec2 q = cloudPlane(d);
  float body = clouds(q);
  // Fewer clouds low down, toward the sun's clear glow; crisp edges in the distance, softer overhead (where the layer
  // is close and its heaps would read as flat cut-outs).
  float soft = 0.07 * smoothstep(0.2, 0.7, d.y);
  float c = smoothstep(0.47 - soft, 0.505 + soft, body + 0.06 * smoothstep(0.05, 0.3, d.y) - 0.08 * smoothstep(0.6, 0.95, toward));
  vec2 toSun = normalize(uSun.xz + 1e-4);
  float lit = clamp((body - clouds(q + toSun * 0.09)) * 5.0 + 0.45, 0.0, 1.0);
  vec3 cloud = mix(uCloudShade, uCloudLit, lit);
  // Thick cores darker, thin edges glowing where the sun is behind them.
  cloud *= mix(1.0, 0.72, smoothstep(0.58, 0.78, body));
  float edge = 1.0 - smoothstep(0.5, 0.6, body);
  cloud += uGlow * (pow(toward, 4.0) * 0.35 + pow(toward, 16.0) * 1.0) * (0.3 + lit + edge * 1.5);
  sky = mix(sky, cloud, c * smoothstep(0.0, 0.1, d.y));
  // At the landing, a photographed sky (Poly Haven's evening_road_01_puresky, CC0) takes over: real heaped cumulus
  // where noise can only approximate them. It's turned so its low sun sits behind ours, and regraded from its blue
  // evening into the reference's palette: lavender gaps, rose-mauve cloud bodies, peach and gold where they're lit.
  // (Turned so the field of cumulus its low sun lights up fills the view toward ours.)
  if (uPhoto > 0.001) {
    float u = atan(d.z, d.x) / 6.28318 + 0.5;
    float uSunAz = atan(uSun.z, uSun.x) / 6.28318 + 0.5;
    float elev = asin(clamp(d.y, 0.0, 1.0)) / 1.5708;
    vec3 photo = texture2D(uPhotoSky, vec2(fract(u - uSunAz + 0.0), max(elev, 0.003))).rgb;
    // (Its brightness as seen, not linear, so the grade's thresholds sit where the eye puts them.)
    float l = pow(dot(photo, vec3(0.2126, 0.7152, 0.0722)), 1.0 / 2.2);
    // Clear sky is blue in the photo, cloud is grey to white: tell them apart by colour, not brightness.
    float lin = max(dot(photo, vec3(0.2126, 0.7152, 0.0722)), 1e-4);
    float blueness = (photo.b - 0.5 * (photo.r + photo.g)) / lin;
    float cloud = 1.0 - smoothstep(0.12, 0.45, blueness);
    float k = smoothstep(0.4, 0.92, l);
    // Lavender overhead, warming to peach and gold toward the horizon and the sun.
    vec3 gap = mix(vec3(0.84, 0.7, 0.86), vec3(1.05, 0.8, 0.6), smoothstep(0.0, 0.4, 0.45 - d.y) * (0.6 + 0.4 * pow(toward, 2.0))) * (0.72 + 0.3 * l);
    vec3 body = mix(vec3(0.7, 0.45, 0.52), vec3(1.3, 0.86, 0.62), k) * (0.6 + 0.8 * k);
    // Toward the sun everything warms to peach and orange: the clouds blaze, the gaps go gold.
    float near = pow(toward, 3.0);
    body = mix(body, vec3(1.3, 0.76, 0.46) * (0.7 + 0.7 * k), near * 0.6);
    gap = mix(gap, vec3(1.05, 0.72, 0.5), near * 0.45);
    vec3 graded = mix(gap, body, cloud);
    // The sun: a big saturated orange glow round a small white-hot core (its starburst is a lens effect, in
    // components/three/grade.ts, so the depth of field doesn't smear it).
    graded += uGlow * (pow(toward, 12.0) * 0.25 + pow(toward, 80.0) * 0.8 + pow(toward, 600.0) * 2.5 + pow(toward, 6000.0) * 30.0);
    // Cloud edges near the sun catch fire.
    graded += uGlow * pow(toward, 4.0) * cloud * k * 0.6;
    // Down at the horizon, the warm haze.
    graded = mix(mix(uHorizon, uGlow, pow(toward, 4.0) * 0.5), graded, smoothstep(0.0, 0.1, d.y));
    sky = mix(sky, graded, uPhoto);
  }
  if (uDebug > 0.5) sky = vec3(c, body, lit);
  gl_FragColor = vec4(sky, uOpacity);
  #include <colorspace_fragment>
}`;

let photo: Texture | null = null;
/** The landing's photographed sky (public/textures/landing/sky-clouds.jpg: the upper half of the panorama). */
function photoSky() {
  if (!photo) {
    photo = new TextureLoader().load('/textures/landing/sky-clouds.jpg');
    photo.colorSpace = SRGBColorSpace;
    photo.wrapS = RepeatWrapping;
    photo.anisotropy = 4;
  }
  return photo;
}

/** The sky dome, fog and warm sun light, all following the journey. */
export function Sky({ sun }: { sun: Mesh | null }) {
  const scene = useThree((s) => s.scene);
  const camera = useThree((s) => s.camera);
  const dome = useRef<Mesh>(null);
  const light = useRef<DirectionalLight>(null);
  const fog = useMemo(() => new Fog(PLASTER.clone(), 1000, 2000), []);
  const material = useMemo(
    () =>
      new ShaderMaterial({
        vertexShader,
        fragmentShader,
        uniforms: {
          uTop: { value: SKY_TOP },
          uHorizon: { value: SKY_HORIZON },
          uGlow: { value: SUN_GLOW },
          uCloudLit: { value: CLOUD_LIT },
          uCloudShade: { value: CLOUD_SHADE },
          uTime: { value: 0 },
          // Dev: ?skydebug shows the cloud mask (red), raw noise (green) and height (blue).
          uDebug: { value: process.env.NODE_ENV === 'development' && window.location.search.includes('skydebug') ? 1 : 0 },
          uSun: { value: MOON },
          uOpacity: { value: 0 },
          uPhotoSky: { value: photoSky() },
          uPhoto: { value: 0 },
        },
        side: BackSide,
        transparent: true,
        depthWrite: false,
        fog: false,
      }),
    []
  );

  useEffect(() => {
    scene.background = PLASTER;
    scene.fog = fog;
    return () => {
      scene.fog = null;
      scene.background = null;
    };
  }, [scene, fog]);

  useFrame((state) => {
    const f = journey.frame;
    const bloom = bloomAt(f);
    material.uniforms.uOpacity.value = bloom;
    // (FogDrog's photographed sunset sky isn't this one's.)
    material.uniforms.uPhoto.value = 0;
    material.uniforms.uTime.value = state.clock.elapsedTime;
    dome.current?.position.copy(camera.position);

    // Fog: none for the hero, close once among the falls (it hides what's far below when looking down), lifting for
    // the pool. Its colour is the sky's horizon, so things melt into the background.
    // Three states: none for the hero; close among the falls (it hides what's far below when looking down); a warm
    // aerial haze over the lake, so the cliffs and mountains fade with distance.
    // (Closed tight before the world below is drawn, lib/journey.ts belowVisible, so it never flashes in.)
    const among = smoothstep(BEATS.open, BEATS.open + 10, f);
    // The world below is in the scene from the start of the drop but wholly in haze; the haze then thins over about a
    // screen of scroll, so the cliffs emerge from it rather than switching on.
    const emerge = smoothstep(BEATS.fogIn, 280, f);
    // (Easing out slowly, so the cliffs and lake emerge through it rather than appearing.)
    const lake = smoothstep(BEATS.fogOut[0] - 140, BEATS.fogOut[1], f) ** 0.6;
    fog.near = lerp(lerp(1000, lerp(5, 12, emerge), among), 120, lake);
    fog.far = lerp(lerp(2000, lerp(6, 120, emerge * emerge), among), 2200, lake);
    // Riding away from the landing, the smog closes round the street, so its far end (recycled ahead,
    // components/three/drive.tsx) is always in haze.
    fog.near = lerp(fog.near, 40, ride.drive.away);
    fog.far = lerp(fog.far, 620, ride.drive.away);
    // The haze matches the photographed sky behind it on the way down (so the cliffs emerge from the sky itself), then
    // warms to the landing's horizon.
    fog.color.copy(PLASTER).lerp(DESCENT_HAZE, bloom).lerp(SKY_HORIZON, lake);

    // Low, warm, behind the scene at the landing: it rims the reeds, the frog and the spray.
    if (light.current) {
      // (Most of the landing's raking light already on the way down, so the cliffs and water have shape from the start.)
      const landing = Math.max(0.75 * bloom, smoothstep(BEATS.fogOut[0], BEATS.fogOut[1], f));
      light.current.intensity = bloom * (0.6 + 1.4 * landing);
      // At the landing the light is cheated round to rake across the cliff faces from the left (as in the reference),
      // while the sun itself stays where it's seen, low over the saddle.
      light.current.position.lerpVectors(SUN_POSITION, LANDING_LIGHT, landing);
    }
    if (sun) {
      const m = sun.material as { opacity: number };
      m.opacity = 0;
      sun.visible = false;
    }
  });

  return (
    <>
      <mesh ref={dome} name="SkyDome" material={material} renderOrder={-100} frustumCulled={false} visible={!devFlag('nosky')}>
        {/* (Inside the camera's far plane but beyond the farthest towers: it draws after them, as it's transparent.) */}
        <sphereGeometry args={[1800, 32, 16]} />
      </mesh>
      {/* Its shadows cover the landing: the canyon round the lake, so cliffs shade each other and the frog sits in its
          own shadow on its pad. Aimed at the lake's centre. */}
      <directionalLight
        ref={light}
        position={SUN_POSITION.toArray()}
        color={WARM_LIGHT}
        intensity={0}
        castShadow
        shadow-mapSize={[2048, 2048]}
        shadow-bias={-0.0004}
        shadow-normalBias={0.04}
        shadow-camera-left={-40}
        shadow-camera-right={40}
        shadow-camera-top={40}
        shadow-camera-bottom={-40}
        shadow-camera-near={1}
        shadow-camera-far={160}
      >
        <object3D attach="target" position={[-35.9138, -11, 38.0126]} />
      </directionalLight>
    </>
  );
}
