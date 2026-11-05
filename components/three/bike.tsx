'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  BackSide,
  BoxGeometry,
  Color,
  DoubleSide,
  FrontSide,
  type Group,
  type Material,
  Matrix4,
  Mesh,
  MeshBasicMaterial,
  type MeshPhysicalMaterial,
  type MeshStandardMaterial,
  Object3D,
  PMREMGenerator,
  Scene,
  type SpotLight,
  type Texture,
  type WebGLRenderer,
} from 'three';
import { courseAt, courseCurve, ZONES } from '@/lib/course';
import { belowVisible, journey, NO_MIRROR_LAYER, smoothstep } from '@/lib/journey';
import { anchors, bikeReady, CRUISE, muckUnder, ride, road, skipped } from '@/lib/ride';
import { DRACO_PATH } from './biome';
import { BoostPod } from './boost-pod';
import { dashDisplay } from './dash';
import { DigitalGhost, sampleDigits } from './digital-ghost';
import { pillPlate } from './pill-glyph';
import { precompile } from './precompile';
import { RideControl, RideHalo, RideStreaks } from './ride';

const URL = ZONES[0].bike;
// Where it parks on the deck (art/build-city.py BIKE_AT, BIKE_YAW, fitted to the concept's framing; Blender's (x, y, z) is
// three's (x, z, -y)).
export const AT = [-35.9138, -11, 38.0126] as const;
// The lamp under the gantry (top left of the shot), warm against the green, picking out the chrome and the carapace.
const LAMP = [-39.79, -7.2, 36.0] as const;
const GLOW = 0.7;
const YAW = (-71.167 * Math.PI) / 180;

let night: Texture | null = null;
/**
 * What the bike's chrome and carapace reflect: a dark room with the city's glow in it, a broad green band low down
 * ahead (the skyline), a cold wash overhead (the cloud) and a few hard pale strips (lamps and lit floors) for the highlights.
 */
function nightEnvMap(gl: WebGLRenderer) {
  if (night) return night;
  const scene = new Scene();
  const room = new Mesh(new BoxGeometry(20, 20, 20), new MeshBasicMaterial({ color: new Color(0.004, 0.008, 0.006), side: BackSide }));
  scene.add(room);
  const panel = (w: number, h: number, colour: Color, x: number, y: number, z: number, ry = 0, rx = 0) => {
    const m = new Mesh(new BoxGeometry(w, h, 0.1), new MeshBasicMaterial({ color: colour }));
    m.position.set(x, y, z);
    m.rotation.set(rx, ry, 0);
    scene.add(m);
  };
  panel(18, 3, new Color(0.6, 0.8, 0.55).multiplyScalar(1.2), 9, 0.5, 0, Math.PI / 2);
  panel(18, 2, new Color(0.15, 0.5, 0.2), -9.5, 0, 0, Math.PI / 2);
  panel(20, 20, new Color(0.04, 0.09, 0.06), 0, 9.8, 0, 0, Math.PI / 2);
  for (const z of [-6, -2, 3, 7]) panel(0.25, 14, new Color(1.0, 1.05, 0.8).multiplyScalar(1.6), 9, 3, z, Math.PI / 2);
  const pmrem = new PMREMGenerator(gl);
  night = pmrem.fromScene(scene, 0.02).texture;
  pmrem.dispose();
  return night;
}

let sunset: Texture | null = null;
/** What the chrome bike reflects in the second city: a pink-violet sky, a low sun, white towers. */
export function sunsetEnvMap(gl: WebGLRenderer) {
  if (sunset) return sunset;
  const scene = new Scene();
  // (Mostly dark, with bright bands: mirror chrome reads by the contrast of what it reflects.)
  scene.add(new Mesh(new BoxGeometry(20, 20, 20), new MeshBasicMaterial({ color: new Color(0.04, 0.025, 0.06), side: BackSide })));
  const panel = (w: number, h: number, colour: Color, x: number, y: number, z: number, ry = 0, rx = 0) => {
    const m = new Mesh(new BoxGeometry(w, h, 0.1), new MeshBasicMaterial({ color: colour }));
    m.position.set(x, y, z);
    m.rotation.set(rx, ry, 0);
    scene.add(m);
  };
  panel(20, 20, new Color(0.3, 0.18, 0.42), 0, 9.8, 0, 0, Math.PI / 2);
  panel(18, 2.5, new Color(1.0, 0.55, 0.6).multiplyScalar(1.6), 9, 0.6, 0, Math.PI / 2);
  panel(18, 2.5, new Color(0.7, 0.45, 1.0).multiplyScalar(1.2), -9, 0.6, 0, Math.PI / 2);
  panel(2.5, 18, new Color(0.9, 0.85, 1.0).multiplyScalar(1.5), 0, 0.6, 9);
  panel(2.5, 18, new Color(0.9, 0.85, 1.0).multiplyScalar(1.1), 0, 0.6, -9);
  panel(3, 3, new Color(1.0, 0.75, 0.6).multiplyScalar(5), 9.5, 1.2, -2, Math.PI / 2);
  for (const z of [-7, -4, 4, 7]) panel(1.2, 12, new Color(0.95, 0.95, 1.0).multiplyScalar(1.3), -9, 2, z, Math.PI / 2);
  panel(20, 20, new Color(0.02, 0.015, 0.03), 0, -9.8, 0, 0, Math.PI / 2);
  const pmrem = new PMREMGenerator(gl);
  sunset = pmrem.fromScene(scene, 0.02).texture;
  pmrem.dispose();
  return sunset;
}

const daylight: (Texture | null)[] = [null, null, null, null, null];
/**
 * What a later zone's bike and city reflect: the chrome city's sunset (above), the hive's dawn (a rose sky, a gold sun
 * low ahead, warm bone-white walls), the desert's noon (a pale hot sky, the sun high, amber sand below, dark machines),
 * the core's dark (a black room, a line of hard pale lights overhead, green either side, a wet floor).
 */
export function zoneEnvMap(gl: WebGLRenderer, k: number) {
  if (k <= 1) return sunsetEnvMap(gl);
  const known = daylight[k];
  if (known) return known;
  const hive = k === 2;
  const core = k === 4;
  const scene = new Scene();
  scene.add(
    new Mesh(
      new BoxGeometry(20, 20, 20),
      new MeshBasicMaterial({ color: core ? new Color(0.006, 0.012, 0.008) : hive ? new Color(0.06, 0.03, 0.04) : new Color(0.08, 0.05, 0.03), side: BackSide })
    )
  );
  const panel = (w: number, h: number, colour: Color, x: number, y: number, z: number, ry = 0, rx = 0) => {
    const m = new Mesh(new BoxGeometry(w, h, 0.1), new MeshBasicMaterial({ color: colour }));
    m.position.set(x, y, z);
    m.rotation.set(rx, ry, 0);
    scene.add(m);
  };
  if (core) {
    for (const x of [-7, -3, 1, 5]) panel(2.2, 3.4, new Color(0.9, 1.0, 0.88).multiplyScalar(2.2), x, 9.6, 0, 0, Math.PI / 2);
    panel(18, 4, new Color(0.14, 0.75, 0.24).multiplyScalar(1.3), 0, 1.5, 9.5);
    panel(18, 4, new Color(0.14, 0.75, 0.24).multiplyScalar(1.3), 0, 1.5, -9.5);
    panel(2, 2, new Color(1.0, 0.12, 0.08).multiplyScalar(3), 8, 3.5, 7, Math.PI / 4);
    panel(2, 2, new Color(1.0, 0.12, 0.08).multiplyScalar(3), 2, 3.5, -8);
    panel(20, 20, new Color(0.012, 0.03, 0.016), 0, -9.8, 0, 0, Math.PI / 2);
  } else if (hive) {
    panel(20, 20, new Color(0.42, 0.22, 0.34), 0, 9.8, 0, 0, Math.PI / 2);
    panel(18, 2.6, new Color(1.0, 0.68, 0.52).multiplyScalar(1.5), 9, 0.6, 0, Math.PI / 2);
    panel(18, 2.2, new Color(0.95, 0.55, 0.62).multiplyScalar(1.0), -9, 0.6, 0, Math.PI / 2);
    panel(2.5, 18, new Color(0.95, 0.88, 0.8).multiplyScalar(1.3), 0, 0.8, 9);
    panel(2.5, 18, new Color(0.95, 0.88, 0.8).multiplyScalar(1.0), 0, 0.8, -9);
    panel(3, 3, new Color(1.0, 0.78, 0.45).multiplyScalar(5), 9.5, 1.0, -4, Math.PI / 2);
    for (const z of [-7, -3, 3, 7]) panel(1.0, 10, new Color(1.0, 0.7, 0.35).multiplyScalar(1.4), -9, 2, z, Math.PI / 2);
    panel(20, 20, new Color(0.1, 0.06, 0.05), 0, -9.8, 0, 0, Math.PI / 2);
  } else {
    panel(20, 20, new Color(0.75, 0.55, 0.35), 0, 9.8, 0, 0, Math.PI / 2);
    panel(18, 3, new Color(1.0, 0.82, 0.55).multiplyScalar(1.4), 9, 0.4, 0, Math.PI / 2);
    panel(18, 3, new Color(0.9, 0.7, 0.45).multiplyScalar(1.1), -9, 0.4, 0, Math.PI / 2);
    panel(2.5, 18, new Color(0.25, 0.18, 0.12), 0, 1.5, 9);
    panel(2.5, 18, new Color(0.25, 0.18, 0.12), 0, 1.5, -9);
    panel(3.5, 3.5, new Color(1.0, 0.97, 0.85).multiplyScalar(6), 5, 8, -3, 0, Math.PI / 2);
    panel(20, 20, new Color(0.55, 0.36, 0.2), 0, -9.8, 0, 0, Math.PI / 2);
  }
  const pmrem = new PMREMGenerator(gl);
  const t = pmrem.fromScene(scene, 0.02).texture;
  pmrem.dispose();
  daylight[k] = t;
  return t;
}

// The morph (lib/ride.ts ride.morph): a seam of light sweeps the bike from its nose to its tail, into the next zone's
// bike. Ahead of it is the new bike, behind it the old (each zone's built in the same frame and anchors: art/build-
// bike2.py and on), each cut away where the other shows; until the chrome bike's loaded, the black one's own materials
// turn to chrome behind the seam instead. Measured along the bike (its own x, from the world through the inverse of
// where it's ridden), so it holds however it moves.
const shared = { uWorldToBike: { value: new Matrix4() }, uSeamColour: { value: new Color(0.85, 0.75, 1.0) }, uDigital: { value: 0 } };
/** Each bike's say in the morph: where the seam is, which side of it the bike shows (1 ahead, -1 behind, 0 all of it). */
const morphUniforms = ZONES.map(() => ({ uEdge: { value: 2 }, uSide: { value: 0 }, uSeam: { value: 0 }, uSwap: { value: 1 } }));
const CHROME_REACH = 1.45; // m either side of the bike's middle the seam starts and ends
// Each zone's seam: the colour of the light it sweeps with.
const SEAM = [new Color(0.6, 1.0, 0.5), new Color(0.85, 0.75, 1.0), new Color(1.0, 0.7, 0.4), new Color(0.55, 1.0, 0.35), new Color(0.35, 1.0, 0.45)];
type MorphKind = 'body' | 'glow' | 'plain';
function morphable(material: Material & MeshPhysicalMaterial, kind: MorphKind, bike: number) {
  const own = morphUniforms[bike];
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, shared, own);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nuniform mat4 uWorldToBike;\nvarying vec3 vBikeP;')
      .replace('#include <project_vertex>', '#include <project_vertex>\nvBikeP = (uWorldToBike * modelMatrix * vec4(transformed, 1.0)).xyz;');
    // (Only the black bike recolours itself, while the chrome one's still loading.)
    const recolour =
      bike !== 0
        ? ''
        : kind === 'glow'
          ? 'diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.32, 0.12, 0.45), chromed);'
          : kind === 'body'
            ? `diffuseColor.rgb = mix(diffuseColor.rgb, vec3(0.97, 0.96, 1.0), chromed);
metalnessFactor = mix(metalnessFactor, 1.0, chromed);
roughnessFactor = mix(roughnessFactor, 0.04, chromed);`
            : '';
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
uniform float uEdge;
uniform float uSide;
uniform float uSeam;
uniform float uSwap;
uniform vec3 uSeamColour;
uniform float uDigital;
varying vec3 vBikeP;`
      )
      .replace(
        '#include <metalnessmap_fragment>',
        `#include <metalnessmap_fragment>
// The bike it's becoming shows only ahead of the seam; the one it's been, only behind it (or, before the new one's in,
// all of it, turning behind the seam).
float vBikeX = vBikeP.x;
if (uSide > 0.5 && vBikeX < uEdge) discard;
if (uSide < -0.5 && uSwap > 0.5 && vBikeX > uEdge) discard;
float chromed = smoothstep(uEdge - 0.04, uEdge + 0.04, vBikeX) * step(uSide, -0.5) * (1.0 - uSwap);
// The core's boost: cut away in little blocks, nose first, lit green at the edge of what's going
// (components/three/digital-ghost.tsx: the blocks coming off it).
float digitEdge = 0.0;
if (uDigital > 0.001) {
  float digitH = fract(sin(dot(floor(vBikeP * 34.0), vec3(12.9898, 78.233, 37.719))) * 43758.5453);
  float digitLeft = digitH * 0.55 + clamp((1.45 - vBikeP.x) / 2.9, 0.0, 1.0) * 0.45 - uDigital;
  if (digitLeft < 0.0) discard;
  digitEdge = 1.0 - smoothstep(0.0, 0.1, digitLeft);
}
${recolour}`
      )
      .replace(
        '#include <emissivemap_fragment>',
        `#include <emissivemap_fragment>
${kind === 'glow' && bike === 0 ? 'totalEmissiveRadiance = mix(totalEmissiveRadiance, vec3(dot(totalEmissiveRadiance, vec3(0.33))) * vec3(0.8, 0.42, 1.3), chromed);' : ''}
// The seam itself: a bright band of light where the change is happening.
totalEmissiveRadiance += uSeamColour * exp(-abs(vBikeX - uEdge) * 38.0) * 4.0 * uSeam;
totalEmissiveRadiance += vec3(0.3, 1.0, 0.42) * digitEdge * 6.0;`
      );
  };
  material.customProgramCacheKey = () => `bike-morph-${bike}-${kind}`;
}

/** Whether zone k's bike is drawn: the one it is or is becoming, the one it's been while the seam sweeps it. */
function bikeShown(k: number) {
  const m = ride.morph;
  // (Until the chrome bike's loaded, the black one stands in for it, turned to chrome.)
  if (k === 0 && m.to === 1 && !bikeReady[1]) return true;
  return k === m.to || (k === m.from && m.from !== m.to);
}

// Each zone's bike's lit parts, by their name's ending.
const BIKE_GLOWS: Record<string, number> = { Vein: 2.2, Led: 7, Tail: 4, Fluid: 2.2, Tube: 1.3 };

/**
 * A later zone's bike (art/build-bike2.py and on: the chrome bike, the bone bike, the desert's), revealed behind the
 * morph's seam; the chrome one's heart beats once it's arrived.
 */
function ZoneBike({ k, env, buttonMaterials }: { k: number; env: Texture; buttonMaterials: { current: MeshStandardMaterial[] } }) {
  const { scene } = useGLTF(ZONES[k].bike, DRACO_PATH);
  const { gl, camera, scene: world } = useThree();
  const P = `Bike${k + 1}`;
  const dash = useMemo(dashDisplay, []);
  const parts = useRef<{ heart: Object3D | null; arteries: Object3D | null; front: Object3D | null; rear: Object3D | null }>({
    heart: null,
    arteries: null,
    front: null,
    rear: null,
  });
  useEffect(() => {
    const mine: MeshStandardMaterial[] = [];
    scene.traverse((child) => {
      const mesh = child as Mesh;
      if (!mesh.isMesh) return;
      const m = mesh.material as Material & MeshPhysicalMaterial;
      const kind = m.name.startsWith(P) ? m.name.slice(P.length) : m.name;
      m.envMap = env;
      m.envMapIntensity = k === 1 ? 1.5 : 1.1;
      m.roughness = Math.max(m.roughness, 0.05);
      if (kind === 'Glass' || kind === 'Smoke') {
        m.depthWrite = false;
        // (Plain see-through glass, not transmission: any transmissive material makes three render the whole scene
        // again every frame, to refract it, and at this size the refraction can't be seen.)
        m.transmission = 0;
        m.transparent = true;
        m.opacity = kind === 'Glass' ? 0.3 : 0.55;
      }
      // The dash shows the speed and the logo (components/three/dash.ts).
      if (kind === 'Dash') {
        m.map = dash.texture;
        m.emissiveMap = dash.texture;
        m.emissive.setRGB(1, 1, 1);
        m.emissiveIntensity = 1.2;
        m.color.setRGB(1, 1, 1);
        m.toneMapped = false;
      }
      if (kind in BIKE_GLOWS) {
        m.emissiveIntensity = BIKE_GLOWS[kind];
        m.toneMapped = false;
      }
      // (The bone bike's bone is old bone, not plastic: warmer, a little darker, satin rather than gloss.)
      if (m.name === 'Bike3Bone') {
        m.color.multiply(new Color(0.88, 0.8, 0.7));
        m.roughness = Math.max(m.roughness, 0.55);
        m.envMapIntensity = 0.6;
      }
      // Its button takes over as the throttle's: lit by components/three/ride.tsx with the black bike's.
      if (kind === 'Button' || kind === 'ButtonGlyph') {
        m.emissiveIntensity = 0;
        m.toneMapped = false;
        if (!mine.includes(m)) mine.push(m);
      }
      morphable(m, 'plain', k);
      mesh.castShadow = kind !== 'Glass' && kind !== 'Smoke' && kind !== 'ButtonGlyph';
      mesh.receiveShadow = true;
      m.needsUpdate = true;
    });
    buttonMaterials.current = [...buttonMaterials.current, ...mine];
    // Its pill's play or pause symbol, in place of the modelled chevrons.
    const glyphMaterial = mine.find((m) => m.name === `${P}ButtonGlyph`);
    const unplate = glyphMaterial
      ? pillPlate(
          scene,
          glyphMaterial,
          mine.find((m) => m.name === `${P}Button`)
        )
      : null;
    parts.current = {
      heart: scene.getObjectByName(`${P}Heart`) ?? null,
      arteries: scene.getObjectByName(`${P}Arteries`) ?? null,
      front: scene.getObjectByName(`Wheel${k + 1}Front`) ?? null,
      rear: scene.getObjectByName(`Wheel${k + 1}Rear`) ?? null,
    };
    // Ready once its programs are compiled, in the background, and its textures uploaded: compiled on first sight
    // instead, they stalled the frame the morph into it began.
    let live = true;
    const textures = new Set<Texture>();
    scene.traverse((o) => {
      const m = (o as Mesh).material as (Material & Record<string, unknown>) | undefined;
      for (const v of Object.values(m ?? {})) if ((v as Texture)?.isTexture) textures.add(v as Texture);
    });
    precompile(gl, scene, camera, world)
      .catch(() => {})
      .then(() => {
        if (!live) return;
        for (const t of textures) gl.initTexture(t);
        bikeReady[k] = true;
        // (What the core's boost breaks it into.)
        if (k === ZONES.length - 1 && scene.parent) sampleDigits(scene, scene.parent);
      });
    return () => {
      live = false;
      bikeReady[k] = false;
      unplate?.();
      buttonMaterials.current = buttonMaterials.current.filter((m) => !mine.includes(m));
    };
  }, [scene, env, buttonMaterials, dash, k, P, gl, camera, world]);

  const last = useRef(0);
  useFrame((state) => {
    scene.visible = bikeShown(k) && ride.ghost.amount < 0.999;
    if (!scene.visible) return;
    const { front, rear, heart, arteries } = parts.current;
    const ds = ride.drive.s - last.current;
    last.current = ride.drive.s;
    if (front) front.rotation.z -= ds / 0.315;
    if (rear) rear.rotation.z -= ds / 0.325;
    // Arrived in the plaza, its heart pumps: a lub-dub at about 72 beats a minute, ticking over slowly before that.
    const t = state.clock.elapsedTime * (ride.transition.arrived ? 1.2 : 0.7);
    const f = t - Math.floor(t);
    const beat = Math.exp(-(((f - 0.08) / 0.05) ** 2)) + 0.65 * Math.exp(-(((f - 0.3) / 0.06) ** 2));
    const strength = ride.transition.arrived ? 1 : 0.35;
    if (heart) heart.scale.setScalar(1 + 0.07 * beat * strength);
    dash.draw(ride.drive.speed * 3.6);
    if (arteries) arteries.scale.setScalar(1 + 0.035 * beat * strength);
  });

  return <primitive object={scene} />;
}

/**
 * Loads a zone's bike as its city does (components/three/zone-city.tsx): the chrome one once the visitor's on the black
 * one, each after once the ride's heading for the zone before it.
 */
function ZoneBikeLoader(props: { k: number; env: Texture; buttonMaterials: { current: MeshStandardMaterial[] } }) {
  const [go, setGo] = useState(false);
  const asked = useRef(false);
  useFrame(() => {
    if (asked.current || ride.mount < 0.5 || skipped(props.k)) return;
    const { k } = props;
    if (!(k === 1 || ride.zone > k - 1 || (ride.zone === k - 1 && ride.transition.placed))) return;
    asked.current = true;
    // (If it's been built: the file's checked for first.)
    fetch(ZONES[k].bike, { method: 'HEAD' })
      .then((r) => r.ok && setGo(true))
      .catch(() => {});
  });
  return go ? (
    <Suspense fallback={null}>
      <ZoneBike {...props} />
    </Suspense>
  ) : null;
}

/** How far along the road the parked bike's shadow map still reaches it (m). */
const SHADED_UNTIL = 30;
const collectShadowed = (scene: Object3D) => {
  const meshes: Mesh[] = [];
  scene.traverse((c) => {
    if ((c as Mesh).isMesh && (c as Mesh).receiveShadow) meshes.push(c as Mesh);
  });
  return meshes;
};

/** The biotech bike (art/build-bike.py), parked on the wet deck at the landing. */
export function Bike() {
  const { scene } = useGLTF(URL, DRACO_PATH);
  const group = useRef<Group>(null);
  const gl = useThree((s) => s.gl);
  const env = useMemo(() => nightEnvMap(gl), [gl]);
  const envSunset = useMemo(() => sunsetEnvMap(gl), [gl]);
  const materials = useRef<(Material & MeshPhysicalMaterial)[]>([]);
  const reflecting = useRef<Texture | null>(null);
  const glow = useRef<MeshStandardMaterial[]>([]);
  const buttonMaterials = useRef<MeshStandardMaterial[]>([]);
  const ridden = useRef<Group>(null);
  const headlight = useRef<SpotLight>(null);
  const lamp = useRef<SpotLight>(null);
  const headlightAim = useRef<Object3D>(null);
  const lampAim = useRef<Object3D>(null);
  // (A light's target only follows the scene when it's in it: aim each at an object placed in the graph.)
  useEffect(() => {
    if (headlight.current && headlightAim.current) headlight.current.target = headlightAim.current;
    if (lamp.current && lampAim.current) lamp.current.target = lampAim.current;
  }, []);
  const wheels = useRef<{ front: Object3D | null; rear: Object3D | null }>({ front: null, rear: null });

  useEffect(() => {
    const glowing: MeshStandardMaterial[] = [];
    const button: MeshStandardMaterial[] = [];
    scene.traverse((child) => {
      const mesh = child as Mesh;
      if (!mesh.isMesh) return;
      const m = mesh.material as Material & MeshPhysicalMaterial;
      m.envMap = env;
      m.envMapIntensity = 1.4;
      // (Floors on gloss: a near-mirror glint overflows the effects' half-float buffer, components/three/effects.tsx.)
      m.roughness = Math.max(m.roughness, 0.1);
      if (m.name === 'BikeGlow' || m.name === 'BikeEye') {
        // Past white, so the bloom catches the ribs and the eye.
        m.emissiveIntensity = m.name === 'BikeEye' ? 4 : GLOW;
        m.toneMapped = false;
        glowing.push(m);
      }
      // The ribs' translucent shells are one merged mesh: three can't sort its rings against each other, so they
      // don't write depth.
      if (m.name === 'BikeRibGlass') m.depthWrite = false;
      // It's closed solids, so its back faces are never seen: not drawn, a third of the frame's GPU time riding. (It still
      // casts from both, so its shadows are as they were.)
      else if (m.name !== 'BikeButton' && m.name !== 'BikeButtonGlyph') {
        m.side = FrontSide;
        m.shadowSide = DoubleSide;
      }
      morphable(
        m,
        m.name === 'BikeButton' || m.name === 'BikeButtonGlyph' || m.name === 'BikeTyre'
          ? 'plain'
          : m.name === 'BikeGlow' || m.name === 'BikeEye' || m.name === 'BikeRibGlass'
            ? 'glow'
            : 'body',
        0
      );
      // The ride button and its lettering: lit by components/three/ride.tsx, dark until the streaks arrive.
      if (m.name === 'BikeButton' || m.name === 'BikeButtonGlyph') {
        m.emissiveIntensity = 0;
        m.toneMapped = false;
        button.push(m);
      }
      mesh.castShadow = m.name !== 'BikeRibGlass';
      mesh.receiveShadow = true;
      m.needsUpdate = true;
    });
    glow.current = glowing;
    buttonMaterials.current = button;
    const all: (Material & MeshPhysicalMaterial)[] = [];
    scene.traverse((c) => {
      const m = (c as Mesh).material as Material & MeshPhysicalMaterial;
      if ((c as Mesh).isMesh && !all.includes(m)) all.push(m);
    });
    materials.current = all;
    reflecting.current = env;
    // The button's centre and the rider's eye (stand-ins on the dome and over the seat until the model has them).
    const stand = (name: string, x: number, y: number) => {
      const o = new Object3D();
      o.name = name;
      o.position.set(x, y, 0);
      (scene.getObjectByName('Bike') ?? scene).add(o);
      return o;
    };
    anchors.button = scene.getObjectByName('ButtonCentre') ?? stand('ButtonCentre', 0.3, 0.98);
    anchors.eye = scene.getObjectByName('RiderEye') ?? stand('RiderEye', -0.3, 1.55);
    anchors.bike = scene;
    wheels.current = { front: scene.getObjectByName('WheelFront') ?? null, rear: scene.getObjectByName('WheelRear') ?? null };
    // Its pill's play or pause symbol, in place of the modelled chevrons.
    const glyphMaterial = button.find((m) => m.name === 'BikeButtonGlyph');
    const unplate = glyphMaterial
      ? pillPlate(
          scene,
          glyphMaterial,
          button.find((m) => m.name === 'BikeButton')
        )
      : null;
    return () => {
      unplate?.();
      anchors.button = null;
      anchors.eye = null;
      anchors.bike = null;
    };
  }, [scene, env]);

  const last = useRef(0);
  const rise = useRef(0);
  const wasShaded = useRef(true);
  const wasReflected = useRef(true);
  const shadowed = useRef<Mesh[] | null>(null);
  // (Before the camera, -1, which rides on the bike: otherwise it trails a frame behind it.)
  useFrame((state) => {
    if (group.current) group.current.visible = belowVisible(journey.frame);
    scene.visible = bikeShown(0) && ride.ghost.amount < 0.999;
    const { s, speed } = ride.drive;
    const pace = Math.min(1, speed / CRUISE);
    // The ribs breathe, slowly; brighter and quicker as it goes.
    const breath = 0.8 + 0.2 * Math.sin(state.clock.elapsedTime * (1.3 + 5 * pace));
    for (const m of glow.current) if (m.name === 'BikeGlow') m.emissiveIntensity = GLOW * breath * (1 + 1.2 * pace);
    // Riding: down the road from its spot, turning the last degree or two to run true along it, the wheels rolling.
    const b = ridden.current;
    if (b) {
      const p = courseAt(s);
      if (p) {
        // On a city's own road: along it from where it takes over (lib/course.ts), on out of its plaza and into the next.
        b.position.set(p.x, AT[1], p.z);
        // (Riding up over the slicks of ooze: eased, the suspension taking the edge off.)
        rise.current += (muckUnder(p.u, p.k) - rise.current) * 0.12;
        // (And over the dunes, or off them: its nose following its line.)
        b.position.y += rise.current + ride.drive.y;
        b.rotation.z = ride.drive.pitch;
        b.rotation.y = p.yaw;
        // Leaning into the bend as it takes it.
        // (Into a right-hand bend it leans right: its +x roll, as the yaw is applied first.)
        const lean = -Math.atan((speed * speed * courseCurve(s)) / 9.8);
        b.rotation.x += (Math.max(-0.5, Math.min(0.5, lean)) - b.rotation.x) * 0.08;
        // (Down the core's stairwell and tunnel, it's the road's own roll, up a wall and all.)
        if (ride.drive.section > 0.5) b.rotation.x = ride.drive.roll;
      } else {
        b.position.set(AT[0], AT[1], AT[2]).addScaledVector(road.ahead, s);
        b.rotation.y = YAW + (road.yaw - YAW) * smoothstep(0, 12, s);
        b.rotation.x *= 0.9;
        b.rotation.z = 0;
      }
      // Rolled off its spot it's out from under the shadow map (not redrawn while riding, components/three/journey-canvas.tsx):
      // no sampling it, the costliest part of the bike's shader for nothing.
      const shaded = s <= SHADED_UNTIL;
      if (shaded !== wasShaded.current) {
        wasShaded.current = shaded;
        shadowed.current ??= collectShadowed(scene);
        for (const m of shadowed.current) m.receiveShadow = shaded;
      }
      // And from the seat its reflection's hidden by the bike itself: no drawing it in the wet road, the most of what the
      // reflection's triangles are. (Back in it at the landing, and as the road ahead turns to the chrome city's pure mirror.)
      const reflected = shaded || ride.transition.t > 0.25;
      if (reflected !== wasReflected.current) {
        wasReflected.current = reflected;
        shadowed.current ??= collectShadowed(scene);
        for (const m of shadowed.current) m.layers.set(reflected ? 0 : NO_MIRROR_LAYER);
      }
      const ds = s - last.current;
      last.current = s;
      if (wheels.current.front) wheels.current.front.rotation.z -= ds / 0.315;
      if (wheels.current.rear) wheels.current.rear.rotation.z -= ds / 0.325;
      // The morph: where its seam is along the bike, which bike shows which side of it, and what the bike reflects
      // once it's mostly chrome.
      b.updateMatrixWorld();
      shared.uWorldToBike.value.copy(b.matrixWorld).invert();
      const m = ride.morph;
      const moving = m.from !== m.to;
      const fallback = m.to === 1 && !bikeReady[1];
      shared.uSeamColour.value.copy(SEAM[m.to]);
      shared.uDigital.value = ride.ghost.amount;
      morphUniforms.forEach((u, k) => {
        u.uEdge.value = CHROME_REACH - 2 * CHROME_REACH * m.at;
        u.uSeam.value = moving && m.at > 0.001 && m.at < 0.999 ? 1 : 0;
        u.uSide.value = k === 0 && fallback ? -1 : !moving ? 0 : k === m.to ? 1 : k === m.from ? -1 : 0;
      });
      morphUniforms[0].uSwap.value = fallback ? 0 : 1;
      const dusk = ride.zone > 1 || (m.to >= 1 && m.at > 0.5);
      const wanted = dusk ? envSunset : env;
      if (reflecting.current !== wanted) {
        reflecting.current = wanted;
        for (const mat of materials.current) mat.envMap = wanted;
      }
    }
    // Its own headlight on the road ahead once it's moving.
    // (Off in the second city's sunset, where its pool on the mirror road read as a glowing blob.)
    if (headlight.current)
      headlight.current.intensity =
        240 * Math.min(1, speed / 3 + (ride.drive.cruise ? 0.3 : 0)) * (ride.zone > 1 ? 0 : 1 - smoothstep(0.3, 0.65, ride.transition.t));
  }, -2);

  return (
    <group ref={group} visible={false}>
      <group ref={ridden} position={AT} rotation={[0, YAW, 0, 'YZX']}>
        <primitive object={scene} />
        {ZONES.slice(1).map((z, i) => (
          <ZoneBikeLoader key={z.id} k={i + 1} env={zoneEnvMap(gl, i + 1)} buttonMaterials={buttonMaterials} />
        ))}
        <BoostPod env={envSunset} />
        <DigitalGhost />
        <spotLight ref={headlight} position={[0.95, 0.72, 0]} angle={0.42} penumbra={0.7} distance={60} decay={1.1} intensity={0} color="#e8ffd8" />
        <object3D ref={headlightAim} position={[24, -1.2, 0]} />
      </group>
      <RideControl buttonMaterials={buttonMaterials} />
      <RideStreaks />
      <RideHalo />
      <spotLight ref={lamp} position={LAMP} angle={0.6} penumbra={0.8} distance={14} decay={1.2} intensity={30} color="#ffe6a8" />
      <object3D ref={lampAim} position={AT} />
    </group>
  );
}

if (typeof window !== 'undefined') useGLTF.preload(URL, DRACO_PATH);
