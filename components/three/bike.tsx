'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import {
  BackSide,
  BoxGeometry,
  Color,
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
  Vector3,
  type WebGLRenderer,
} from 'three';
import { belowVisible, journey, smoothstep } from '@/lib/journey';
import { anchors, CRUISE, cityRoadAt, cityRoadCurve, muckUnder, ride, road } from '@/lib/ride';
import { DRACO_PATH } from './biome';
import { RideControl, RideHalo, RideStreaks } from './ride';

const URL = '/models/bike.glb';
const URL2 = '/models/bike2.glb';
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

// (Leaning about its own length, after turning: yaw first.)
const UP = new Vector3(0, 1, 0);
const cityLocal = new Vector3();

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

// The chrome morph (lib/ride.ts ride.chrome): a seam of light sweeps the bike from its nose to its tail. Ahead of it
// is the black biotech bike, behind it the liquid-chrome one (art/build-bike2.py, the same frame and anchors), each
// cut away where the other shows; until the chrome bike's loaded, the black one's own materials turn to chrome behind
// the seam instead. Measured along the bike (its own x, from the world through the inverse of where it's ridden), so
// it holds however it moves.
const chromeUniforms = {
  uChromeEdge: { value: 2 },
  uWorldToBike: { value: new Matrix4() },
  uSeam: { value: 0 },
  // 1 once the chrome bike's in: the black bike is cut away behind the seam rather than recoloured.
  uSwap: { value: 0 },
};
const CHROME_REACH = 1.45; // m either side of the bike's middle the seam starts and ends
type MorphKind = 'body' | 'glow' | 'plain' | 'chrome';
function morphable(material: Material & MeshPhysicalMaterial, kind: MorphKind) {
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, chromeUniforms);
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nuniform mat4 uWorldToBike;\nvarying float vBikeX;')
      .replace('#include <project_vertex>', '#include <project_vertex>\nvBikeX = (uWorldToBike * modelMatrix * vec4(transformed, 1.0)).x;');
    const recolour =
      kind === 'glow'
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
uniform float uChromeEdge;
uniform float uSeam;
uniform float uSwap;
varying float vBikeX;`
      )
      .replace(
        '#include <metalnessmap_fragment>',
        `#include <metalnessmap_fragment>
float chromed = smoothstep(uChromeEdge - 0.04, uChromeEdge + 0.04, vBikeX);
${
  kind === 'chrome'
    ? '// The chrome bike: only behind the seam.\nif (vBikeX < uChromeEdge) discard;'
    : `// The black bike: cut away behind the seam once the chrome one's there, else turned to chrome.
if (uSwap > 0.5 && vBikeX > uChromeEdge) discard;
${recolour.replace(/chromed\)/g, 'chromed * (1.0 - uSwap))')}`
}`
      )
      .replace(
        '#include <emissivemap_fragment>',
        `#include <emissivemap_fragment>
${kind === 'glow' ? 'totalEmissiveRadiance = mix(totalEmissiveRadiance, vec3(dot(totalEmissiveRadiance, vec3(0.33))) * vec3(0.8, 0.42, 1.3), chromed * (1.0 - uSwap));' : ''}
// The seam itself: a bright band of light where the change is happening.
totalEmissiveRadiance += vec3(0.85, 0.75, 1.0) * exp(-abs(vBikeX - uChromeEdge) * 38.0) * 4.0 * uSeam;`
      );
  };
  material.customProgramCacheKey = () => `bike-morph-${kind}`;
}

/** The liquid-chrome bike (art/build-bike2.py), revealed behind the morph's seam; its heart beats once it's arrived. */
function ChromeBike({ env, buttonMaterials, black }: { env: Texture; buttonMaterials: { current: MeshStandardMaterial[] }; black: Object3D }) {
  const { scene } = useGLTF(URL2, DRACO_PATH);
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
      m.envMap = env;
      m.envMapIntensity = 1.5;
      m.roughness = Math.max(m.roughness, 0.05);
      if (m.name === 'Bike2Glass' || m.name === 'Bike2Smoke') m.depthWrite = false;
      const glowing: Record<string, number> = { Bike2Vein: 2.2, Bike2Led: 7, Bike2Tail: 4, Bike2Dash: 1.6 };
      if (m.name in glowing) {
        m.emissiveIntensity = glowing[m.name];
        m.toneMapped = false;
      }
      // Its button takes over as the throttle's: lit by components/three/ride.tsx with the black bike's.
      if (m.name === 'Bike2Button' || m.name === 'Bike2ButtonGlyph') {
        m.emissiveIntensity = 0;
        m.toneMapped = false;
        if (!mine.includes(m)) mine.push(m);
      }
      morphable(m, 'chrome');
      mesh.castShadow = m.name !== 'Bike2Glass' && m.name !== 'Bike2Smoke';
      mesh.receiveShadow = true;
      m.needsUpdate = true;
    });
    buttonMaterials.current = [...buttonMaterials.current, ...mine];
    parts.current = {
      heart: scene.getObjectByName('Bike2Heart') ?? null,
      arteries: scene.getObjectByName('Bike2Arteries') ?? null,
      front: scene.getObjectByName('Wheel2Front') ?? null,
      rear: scene.getObjectByName('Wheel2Rear') ?? null,
    };
    chromeUniforms.uSwap.value = 1;
    return () => {
      chromeUniforms.uSwap.value = 0;
      buttonMaterials.current = buttonMaterials.current.filter((m) => !mine.includes(m));
    };
  }, [scene, env, buttonMaterials]);

  const last = useRef(0);
  useFrame((state) => {
    scene.visible = ride.chrome.at > 0.001;
    // (The black bike, wholly cut away by now, isn't drawn.)
    black.visible = ride.chrome.at < 0.999;
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
    if (arteries) arteries.scale.setScalar(1 + 0.035 * beat * strength);
  });

  return <primitive object={scene} />;
}

/** Loads the chrome bike once the visitor's on the black one, as the second city does (components/three/city-two.tsx). */
function ChromeBikeLoader(props: { env: Texture; buttonMaterials: { current: MeshStandardMaterial[] }; black: Object3D }) {
  const [go, setGo] = useState(false);
  useFrame(() => {
    if (!go && ride.mount > 0.5) setGo(true);
  });
  return go ? (
    <Suspense fallback={null}>
      <ChromeBike {...props} />
    </Suspense>
  ) : null;
}

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
      morphable(
        m,
        m.name === 'BikeButton' || m.name === 'BikeButtonGlyph' || m.name === 'BikeTyre'
          ? 'plain'
          : m.name === 'BikeGlow' || m.name === 'BikeEye' || m.name === 'BikeRibGlass'
            ? 'glow'
            : 'body'
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
    return () => {
      anchors.button = null;
      anchors.eye = null;
      anchors.bike = null;
    };
  }, [scene, env]);

  const last = useRef(0);
  // (Before the camera, -1, which rides on the bike: otherwise it trails a frame behind it.)
  useFrame((state) => {
    if (group.current) group.current.visible = belowVisible(journey.frame);
    const { s, speed } = ride.drive;
    const pace = Math.min(1, speed / CRUISE);
    // The ribs breathe, slowly; brighter and quicker as it goes.
    const breath = 0.8 + 0.2 * Math.sin(state.clock.elapsedTime * (1.3 + 5 * pace));
    for (const m of glow.current) if (m.name === 'BikeGlow') m.emissiveIntensity = GLOW * breath * (1 + 1.2 * pace);
    // Riding: down the road from its spot, turning the last degree or two to run true along it, the wheels rolling.
    const b = ridden.current;
    if (b) {
      const tr = ride.transition;
      if (tr.placed && s > tr.at) {
        // On the second city's own road: along it from where it takes over (its local x along the road in, y left).
        const p = cityRoadAt(s - tr.at);
        cityLocal.set(p.x, 0, -p.y).applyAxisAngle(UP, road.yaw);
        b.position.set(AT[0], AT[1], AT[2]).addScaledVector(road.ahead, tr.at).add(cityLocal);
        // (Riding up over the slicks of ooze.)
        b.position.y += muckUnder(s - tr.at);
        b.rotation.y = road.yaw + p.heading;
        // Leaning into the bend as it takes it.
        // (Into a right-hand bend it leans right: its +x roll, as the yaw is applied first.)
        const lean = -Math.atan((speed * speed * cityRoadCurve(s - tr.at)) / 9.8);
        b.rotation.x += (Math.max(-0.35, Math.min(0.35, lean)) - b.rotation.x) * 0.08;
      } else {
        b.position.set(AT[0], AT[1], AT[2]).addScaledVector(road.ahead, s);
        b.rotation.y = YAW + (road.yaw - YAW) * smoothstep(0, 12, s);
        b.rotation.x *= 0.9;
      }
      const ds = s - last.current;
      last.current = s;
      if (wheels.current.front) wheels.current.front.rotation.z -= ds / 0.315;
      if (wheels.current.rear) wheels.current.rear.rotation.z -= ds / 0.325;
      // The chrome morph: where its seam is along the bike, and what the bike reflects once it's mostly chrome.
      b.updateMatrixWorld();
      chromeUniforms.uWorldToBike.value.copy(b.matrixWorld).invert();
      const at = ride.chrome.at;
      chromeUniforms.uChromeEdge.value = CHROME_REACH - 2 * CHROME_REACH * at;
      chromeUniforms.uSeam.value = at > 0.001 && at < 0.999 ? 1 : 0;
      const wanted = at > 0.5 ? envSunset : env;
      if (reflecting.current !== wanted) {
        reflecting.current = wanted;
        for (const m of materials.current) m.envMap = wanted;
      }
    }
    // Its own headlight on the road ahead once it's moving.
    // (Off in the second city's sunset, where its pool on the mirror road read as a glowing blob.)
    if (headlight.current)
      headlight.current.intensity = 240 * Math.min(1, speed / 3 + (ride.drive.cruise ? 0.3 : 0)) * (1 - smoothstep(0.3, 0.65, ride.transition.t));
  }, -2);

  return (
    <group ref={group} visible={false}>
      <group ref={ridden} position={AT} rotation={[0, YAW, 0, 'YXZ']}>
        <primitive object={scene} />
        <ChromeBikeLoader env={envSunset} buttonMaterials={buttonMaterials} black={scene} />
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
