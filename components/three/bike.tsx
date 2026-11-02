'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import {
  BackSide,
  BoxGeometry,
  Color,
  type Group,
  type Material,
  Mesh,
  MeshBasicMaterial,
  type MeshPhysicalMaterial,
  type MeshStandardMaterial,
  Object3D,
  PMREMGenerator,
  Scene,
  type Texture,
  type WebGLRenderer,
} from 'three';
import { belowVisible, journey } from '@/lib/journey';
import { anchors } from '@/lib/ride';
import { DRACO_PATH } from './biome';
import { RideControl, RideHalo, RideStreaks } from './ride';

const URL = '/models/bike.glb';
// Where it parks on the deck (art/build-city.py BIKE_AT, BIKE_YAW, fitted to the concept's framing; Blender's (x, y, z) is
// three's (x, z, -y)).
const AT = [14.6317, -11, 6.9347] as const;
// The lamp under the gantry (top left of the shot), warm against the green, picking out the chrome and the carapace.
const LAMP = [13.13, -7.2, 2.83] as const;
const GLOW = 0.7;
const YAW = (-113.658 * Math.PI) / 180;

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

/** The biotech bike (art/build-bike.py), parked on the wet deck at the landing. */
export function Bike() {
  const { scene } = useGLTF(URL, DRACO_PATH);
  const group = useRef<Group>(null);
  const gl = useThree((s) => s.gl);
  const env = useMemo(() => nightEnvMap(gl), [gl]);
  const glow = useRef<MeshStandardMaterial[]>([]);
  const buttonMaterials = useRef<MeshStandardMaterial[]>([]);

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
    return () => {
      anchors.button = null;
      anchors.eye = null;
      anchors.bike = null;
    };
  }, [scene, env]);

  useFrame((state) => {
    if (group.current) group.current.visible = belowVisible(journey.frame);
    // The ribs breathe, slowly.
    const breath = 0.8 + 0.2 * Math.sin(state.clock.elapsedTime * 1.3);
    for (const m of glow.current) if (m.name === 'BikeGlow') m.emissiveIntensity = GLOW * breath;
  });

  return (
    <group ref={group} visible={false}>
      <group position={AT} rotation-y={YAW}>
        <primitive object={scene} />
      </group>
      <RideControl buttonMaterials={buttonMaterials} />
      <RideStreaks />
      <RideHalo />
      <spotLight position={LAMP} target-position={AT} angle={0.6} penumbra={0.8} distance={14} decay={1.2} intensity={30} color="#ffe6a8" />
    </group>
  );
}

if (typeof window !== 'undefined') useGLTF.preload(URL, DRACO_PATH);
