'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useMemo, useRef } from 'react';
import {
  AdditiveBlending,
  Color,
  CylinderGeometry,
  Euler,
  type Group,
  type Material,
  type Mesh,
  MeshPhysicalMaterial,
  type MeshStandardMaterial,
  Quaternion,
  ShaderMaterial,
  Vector3,
} from 'three';
import { belowVisible, journey } from '@/lib/journey';
import { DRACO_PATH } from './biome';
import { type DeckPlacement, WetRoad } from './wet-road';

const URL = '/models/city.glb';
// The deck's surface (art/build-city.py DECK_Z, DECK_X, DECK_Y; Blender's -y is three's z), used until the model carries
// its City.DeckTop marker (centre, heading, length and width of the drivable surface).
// (The wet surface floats 3 cm over the slab's top: any less and it loses to it in the depth buffer at a distance.)
const DECK_Y = -11;
const WET_LIFT = 0.03;
const DECK = { x: [-60, -12], z: [-14, 6.5] } as const;

const WINDOW = new Color(0.8, 1.0, 0.62);
const WINDOW_WARM = new Color(1.0, 0.92, 0.55);

/**
 * The towers' facades: near-black walls with a grid of lit windows (the walls' UVs are metres along and up them, from
 * art/build-city.py wall_uvs; roofs are at -1). Most windows are dark; the lit ones are a sickly green, a few warmer.
 * The spire also carries glowing ribs up its faces.
 */
function facade(own: MeshStandardMaterial, spire: boolean) {
  const material = own.clone();
  material.roughness = 0.75;
  material.metalness = 0;
  material.onBeforeCompile = (shader) => {
    shader.uniforms.uWindow = { value: WINDOW };
    shader.uniforms.uWarm = { value: WINDOW_WARM };
    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec2 vWall;\nvarying vec3 vCityWorld;\nvarying float vUpright;')
      .replace(
        '#include <uv_vertex>',
        '#include <uv_vertex>\nvWall = uv;\nvCityWorld = (modelMatrix * vec4(position, 1.0)).xyz;\nvUpright = 1.0 - abs(normalize(mat3(modelMatrix) * normal).y);'
      );
    shader.fragmentShader = shader.fragmentShader
      .replace(
        '#include <common>',
        `#include <common>
uniform vec3 uWindow;
uniform vec3 uWarm;
varying vec2 vWall;
varying vec3 vCityWorld;
varying float vUpright;
float cityHash(vec3 p) { return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453); }`
      )
      .replace(
        '#include <emissivemap_fragment>',
        `#include <emissivemap_fragment>
// (Windows only on upright walls: the pinnacles' sloping faces would otherwise glow whole.)
if ((vWall.x > -0.5 || vWall.y > -0.5) && vUpright > 0.97) {
  // Floors 2.8 m, bays 2.2 m (a little under real, so the towers read bigger); a window in each, lit or not by a hash
  // of its cell (and the building it's on, roughly).
  vec2 cell = floor(vWall / vec2(2.2, 2.8));
  vec2 f = fract(vWall / vec2(2.2, 2.8));
  float building = floor(vCityWorld.x / 9.0) + floor(vCityWorld.z / 9.0) * 17.0;
  float h = cityHash(vec3(cell, building));
  // Lit floors come in runs (whole floors on, others dark), as offices at night.
  float floorLit = step(0.45, cityHash(vec3(cell.y, building, 3.0)));
  float lit = step(0.62, h) * floorLit + step(0.93, h);
  float pane = step(0.22, f.x) * step(f.x, 0.78) * step(0.28, f.y) * step(f.y, 0.8);
  vec3 tint = mix(uWindow, uWarm, step(0.9, cityHash(vec3(cell, building + 5.0))));
  totalEmissiveRadiance += tint * pane * lit * (0.5 + 1.6 * cityHash(vec3(cell, 9.0)));
${
  spire
    ? `  // Glowing ribs up the spire's faces, brightest high up.
  float rib = 1.0 - smoothstep(0.0, 0.08, abs(fract(vWall.x / 9.0) - 0.5) * 2.0 - 0.9);
  totalEmissiveRadiance += vec3(0.35, 1.0, 0.3) * rib * (0.6 + 2.5 * smoothstep(150.0, 450.0, vWall.y));`
    : ''
}
}`
      );
  };
  material.customProgramCacheKey = () => (spire ? 'facade-spire' : 'facade');
  return material;
}

/** Shafts of green light standing out of the city into the cloud, as in the concept: soft-edged, fading at both ends. */
const BEAMS = [
  [420, -90, 2.2],
  [560, 120, 1.6],
  [700, -260, 2.8],
  [880, 40, 2.0],
  [980, 330, 2.6],
  [640, 420, 1.4],
  [1100, -180, 3.0],
] as const;
function beamMaterial() {
  return new ShaderMaterial({
    uniforms: { uOpacity: { value: 1 } },
    vertexShader: /* glsl */ `
      varying float vFacing;
      varying float vHeight;
      void main() {
        vec4 world = modelMatrix * vec4(position, 1.0);
        vec3 n = normalize(mat3(modelMatrix) * normal);
        vFacing = abs(dot(n, normalize(cameraPosition - world.xyz)));
        vHeight = uv.y;
        gl_Position = projectionMatrix * viewMatrix * world;
      }`,
    fragmentShader: /* glsl */ `
      uniform float uOpacity;
      varying float vFacing;
      varying float vHeight;
      void main() {
        float a = pow(vFacing, 4.0) * smoothstep(0.0, 0.25, vHeight) * (1.0 - smoothstep(0.55, 1.0, vHeight));
        gl_FragColor = vec4(vec3(0.45, 1.0, 0.4) * a * 0.9 * uOpacity, 1.0);
      }`,
    transparent: true,
    depthWrite: false,
    blending: AdditiveBlending,
    fog: false,
  });
}

/** The black ooze dripping from the gantry and pooled on the deck: glossy oil. */
const ooze = () =>
  new MeshPhysicalMaterial({ color: new Color(0.004, 0.004, 0.005), roughness: 0.14, clearcoat: 1, clearcoatRoughness: 0.12, specularIntensity: 1 });

export function City() {
  const { scene } = useGLTF(URL, DRACO_PATH);
  const group = useRef<Group>(null);
  const beam = useMemo(() => ({ geometry: new CylinderGeometry(1, 1, 1, 16, 1, true), material: beamMaterial() }), []);

  useMemo(() => {
    const black = ooze();
    const facades = new Map<Material, Material>();
    scene.traverse((child) => {
      const mesh = child as Mesh;
      if (!mesh.isMesh) return;
      const own = mesh.material as MeshStandardMaterial;
      if (own.name === 'CityTower' || own.name === 'CitySpire' || own.name === 'CityConcrete') {
        if (!facades.has(own)) facades.set(own, own.name === 'CityConcrete' ? own : facade(own, own.name === 'CitySpire'));
        mesh.material = facades.get(own) as Material;
      } else if (own.name === 'CityOoze') mesh.material = black;
      else if (own.name === 'CityLamp') {
        own.emissiveIntensity = 8;
        own.toneMapped = false;
      }
      // The deck's top is drawn by the wet reflector below; its box stays as the slab's edges.
      mesh.castShadow = false;
      mesh.receiveShadow = false;
    });
  }, [scene]);

  // Where the wet surface goes: the model's City.DeckTop marker if it has one.
  const deck = useMemo((): DeckPlacement => {
    const top = scene.getObjectByName('CityDeckTop') ?? scene.getObjectByName('City.DeckTop');
    if (top) {
      scene.updateMatrixWorld(true);
      const position = top.getWorldPosition(new Vector3());
      const heading = new Euler().setFromQuaternion(top.getWorldQuaternion(new Quaternion()), 'YXZ').y;
      const { length = 60, width = 20 } = top.userData as { length?: number; width?: number };
      return { position: [position.x, DECK_Y + WET_LIFT, position.z] as const, heading, length, width };
    }
    return {
      position: [(DECK.x[0] + DECK.x[1]) / 2, DECK_Y + WET_LIFT, (DECK.z[0] + DECK.z[1]) / 2] as const,
      heading: 0,
      length: DECK.x[1] - DECK.x[0] - 0.6,
      width: DECK.z[1] - DECK.z[0] - 0.6,
    };
  }, [scene]);

  useFrame(() => {
    if (group.current) group.current.visible = belowVisible(journey.frame);
  });

  return (
    <group ref={group} visible={false}>
      <primitive object={scene} />
      {/* The wet deck. */}
      <WetRoad deck={deck} />
      {BEAMS.map(([x, z, width]) => (
        <mesh key={`${x},${z}`} geometry={beam.geometry} material={beam.material} position={[x, 300, z]} scale={[width, 900, width]} renderOrder={5} />
      ))}
    </group>
  );
}

if (typeof window !== 'undefined') useGLTF.preload(URL, DRACO_PATH);
