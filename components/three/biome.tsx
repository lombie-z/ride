'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import {
  Color,
  type DirectionalLight,
  DoubleSide,
  type HemisphereLight,
  type Material,
  type Mesh,
  MeshBasicMaterial,
  Mesh as MeshClass,
  type MeshPhysicalMaterial,
  type Object3D,
  PerspectiveCamera,
  PMREMGenerator,
  ShaderMaterial,
  type Texture,
  Vector3,
  WebGLRenderTarget,
} from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { BEATS, devFlag, journey, landingAt, ledgeIn, NO_MIRROR_LAYER, RAINBOW_LAYER, smoothstep, toyPresence } from '@/lib/journey';
import { look } from '@/lib/look';
import { FallStreaks } from './fall-streaks';
import { landingMaterial } from './landing';
import { useLandingReflections } from './landing-reflections';
import { precompile } from './precompile';
import { rockMaterial } from './rock';
import { SilhouetteOutline } from './silhouette-outline';
import { bloomAt, SUN_POSITION } from './sky';
import { Spray } from './spray';
import { useStudioReflections } from './studio-environment';
import { waterFromSky, waterLanding, waterLedge, waterMaterial, waterTime } from './water';

export const DRACO_PATH = '/draco/';
const STUDIO_SKY = new Color('#fffaf2');
const STUDIO_GROUND = new Color('#e3d6c6');
const URL = '/models/micro-biome.glb';

// The letter ring orbits this point; the sticker band sits at its depth so the ring weaves in front of and behind it.
const OUTLINE_DEPTH = new Vector3(0, 0.62, 0);

type Kind = 'ring' | 'cloud' | 'star' | 'letter' | 'water';
type Animated = { node: Object3D; kind: Kind; i: number; base: { position: Vector3; scale: Vector3; rotY: number } };

function classify(name: string): Kind | null {
  if (name === 'LetterRing') return 'ring';
  if (name === 'LetterRingTilt') return null;
  if (name.startsWith('Cloud')) return 'cloud';
  if (name.startsWith('Star')) return 'star';
  if (name.startsWith('Letter') || name.startsWith('Word')) return 'letter';
  if (name.startsWith('Water')) return 'water';
  return null;
}

/** A mesh's Blender object name (glTF splits multi-material meshes into children named after their group). */
const ownerName = (o: Object3D) => (o.parent?.name && o.name !== o.parent.name && o.name.startsWith(o.parent.name) ? o.parent.name : o.name);

// Below the planter: none of it casts shadows or takes part in the sticker outline. (three.js drops the dots from
// glTF node names, so Blender's Fall.A arrives as FallA.)
const SKY_PARTS = ['Fall', 'Splash', 'Spray', 'Pool', 'Lake', 'SkyCloud', 'SkyDome', 'Sun', 'Rainbow', 'Landing'];
const isSkyPart = (name: string) => SKY_PARTS.some((p) => name.startsWith(p));

// The lettering tumbles free of the sticker outline, and the water spills off the sticker.
function isOutsideOutline(o: Object3D) {
  return o.name.startsWith('Letter') || o.name.startsWith('Word') || isSkyPart(o.name) || isSkyPart(o.parent?.name ?? '');
}

/** The rainbow: spectral bands across the arc (u: outer red to inner violet), fading at its edges and feet. */
function rainbowMaterial() {
  return new ShaderMaterial({
    uniforms: { uOpacity: { value: 0 } },
    vertexShader: /* glsl */ `
      varying vec2 vUv;
      varying float vY;
      void main() {
        vUv = uv;
        vY = (modelMatrix * vec4(position, 1.0)).y;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform float uOpacity;
      varying vec2 vUv;
      varying float vY;
      vec3 spectrum(float x) {
        vec3 c[6] = vec3[6](vec3(0.95, 0.25, 0.3), vec3(1.0, 0.55, 0.2), vec3(1.0, 0.86, 0.3), vec3(0.35, 0.78, 0.42), vec3(0.3, 0.55, 0.95), vec3(0.55, 0.38, 0.9));
        float f = clamp(x, 0.0, 0.999) * 5.0;
        int i = int(floor(f));
        return mix(c[i], c[min(i + 1, 5)], fract(f));
      }
      void main() {
        // Nothing of it below the lake's surface.
        if (vY < -11.0) discard;
        float along = 1.0 - vUv.y;
        // pow() of a negative is NaN (and bloom smears one NaN pixel over the whole screen), so clamp first.
        float a = pow(max(sin(3.14159 * vUv.x), 0.0), 0.6) * pow(max(sin(3.14159 * along), 0.0), 0.8) * uOpacity * 0.7;
        gl_FragColor = vec4(spectrum(vUv.x) * 1.25, min(a, 1.0));
        #include <colorspace_fragment>
      }`,
    transparent: true,
    depthWrite: false,
    side: DoubleSide,
    fog: false,
  });
}

export function Biome({ onReady, onSun }: { onReady: () => void; onSun: (sun: Mesh) => void }) {
  const { scene } = useGLTF(URL, DRACO_PATH);
  const rainbow = useRef<ShaderMaterial | null>(null);
  const key = useRef<DirectionalLight>(null);
  const hemi = useRef<HemisphereLight>(null);
  const sun = useRef<Mesh | null>(null);

  // Give the sky parts their web materials (water shaders, whiteout clouds, the rainbow and the sun for the rays).
  useMemo(() => {
    const still = waterMaterial('still');
    const falling = waterMaterial('falling');
    scene.traverse((child) => {
      const mesh = child as Mesh;
      if (!mesh.isMesh) return;
      const name = ownerName(mesh);
      // Blender's cloud material glows white inside (for its fly-through); glTF carries that out as an emissive glow on
      // the whole surface, so drop it.
      const own = mesh.material as MeshPhysicalMaterial;
      if (own.name === 'Cloud' && own.emissive) own.emissive.setRGB(0, 0, 0);
      // Blender's glossy clay comes through with near-mirror clearcoats; their sun glints overflow the effects'
      // half-float buffer (Inf), which the bloom turns into black specks. A floor on roughness keeps them finite.
      if (own.isMeshStandardMaterial) own.roughness = Math.max(own.roughness, 0.12);
      if (own.isMeshPhysicalMaterial) own.clearcoatRoughness = Math.max(own.clearcoatRoughness, 0.12);
      // MICRO BIOME in black, to match the black liquid.
      if (name.startsWith('Letter') || name.startsWith('Word')) {
        own.color.setRGB(0.012, 0.012, 0.014);
        if (own.isMeshPhysicalMaterial) own.sheen = 0;
      }
      const landing = landingMaterial(own);
      if (landing) mesh.material = landing;
      else if (name === 'Water') mesh.material = still;
      else if (name === 'Pool' || name === 'Splash') {
        // The lake is drawn by <Lake> (a reflector); the spray particles stand in for Blender's splash beads.
        mesh.visible = false;
      } else if (own.name === 'Canyon') mesh.material = rockMaterial(own);
      else if (name === 'FallMain') {
        // FogDrog's big waterfall: not this site's (the streams carry on as <FallStreaks>' oil ropes).
        mesh.visible = false;
      } else if (name.startsWith('Fall')) {
        mesh.material = falling;
        mesh.renderOrder = 2;
      } else if (name.startsWith('SkyCloud')) {
        // The clay cloud layer: the descent is real now (the photographed sky's clouds), so it's not drawn.
        mesh.visible = false;
      } else if (name === 'Rainbow') {
        rainbow.current = rainbowMaterial();
        mesh.material = rainbow.current;
        mesh.renderOrder = 3;
        // On its own layer, which the camera draws but the lake's mirror camera (see components/three/lake.tsx) doesn't: a lake doesn't
        // reflect a rainbow where a mirror would put it.
        mesh.layers.set(RAINBOW_LAYER);
      } else if (name === 'Sun') {
        // Brighter than white so the bloom catches it; the light rays need it transparent and not writing depth.
        mesh.material = new MeshBasicMaterial({
          color: new Color(1.0, 0.86, 0.66).multiplyScalar(16),
          transparent: true,
          opacity: 0,
          depthWrite: false,
          fog: false,
          toneMapped: false,
        });
        // Raised a little from Blender's placement so it clears the hill on the landing's left.
        mesh.position.copy(SUN_POSITION);
        // A small, intense disc (as in the reference), not a wall of light.
        mesh.scale.setScalar(0.1);
        sun.current = mesh;
      }
    });
  }, [scene]);

  const ledge = useMemo(() => scene.getObjectByName('LandingLedge') as Mesh | undefined, [scene]);
  // The toy itself (planter, spires, moss, letters, its water): everything under the biome's root that isn't part of
  // the world below or the sky.
  const toy = useMemo(() => {
    const root = scene.getObjectByName('MicroBiome') ?? scene;
    return root.children.filter((o) => !isSkyPart(o.name));
  }, [scene]);
  // Its materials fade out (drawn as transparent only while fading, so the hero is untouched).
  const toyMaterials = useMemo(() => {
    const set = new Set<Material>();
    for (const o of toy)
      o.traverse((c) => {
        const m = (c as Mesh).material;
        for (const material of Array.isArray(m) ? m : m ? [m] : []) {
          set.add(material);
        }
      });
    return [...set];
  }, [toy]);
  const below = useMemo(() => {
    const list: Object3D[] = [];
    scene.traverse((o) => {
      if (o.name.startsWith('Landing') && !o.parent?.name.startsWith('Landing')) list.push(o);
    });
    return list;
  }, [scene]);

  // The moss on the hand and the leaves are hundreds of little static meshes: merged into one per material and parent
  // (they never move), so they cost a few draw calls rather than hundreds, in every pass that draws the toy.
  useMemo(() => {
    const groups = new Map<string, Mesh[]>();
    scene.updateMatrixWorld(true);
    scene.traverse((o) => {
      const mesh = o as Mesh;
      if (!mesh.isMesh || !/^(MossHand|Leaf)/.test(ownerName(mesh)) || !mesh.parent) return;
      const g = mesh.geometry;
      const key = `${(mesh.material as Material).uuid}|${mesh.parent.uuid}|${Object.keys(g.attributes).sort().join()}|${!!g.index}`;
      groups.set(key, [...(groups.get(key) ?? []), mesh]);
    });
    for (const meshes of groups.values()) {
      if (meshes.length < 2) continue;
      const parent = meshes[0].parent as Object3D;
      const toParent = parent.matrixWorld.clone().invert();
      const merged = mergeGeometries(
        meshes.map((m) => m.geometry.clone().applyMatrix4(toParent.clone().multiply(m.matrixWorld))),
        false
      );
      if (!merged) continue;
      const one = new MeshClass(merged, meshes[0].material);
      one.name = `${ownerName(meshes[0])}Merged`;
      one.castShadow = meshes[0].castShadow;
      one.receiveShadow = meshes[0].receiveShadow;
      parent.add(one);
      for (const m of meshes) {
        m.removeFromParent();
        m.geometry.dispose();
      }
    }
  }, [scene]);

  const animated = useMemo(() => {
    const list: Animated[] = [];
    const counts: Record<string, number> = {};
    scene.traverse((child) => {
      if ((child as Mesh).isMesh) {
        const owner = ownerName(child);
        const sky = isSkyPart(owner);
        // The landing's solid things take part in the warm sun's shadows (components/three/sky.tsx); the dew, the
        // mountains (beyond its reach) and the rest of the sky parts don't.
        const landing = owner.startsWith('Landing') && !/Dew|Mountains/.test(owner);
        child.castShadow = !sky || landing;
        child.receiveShadow = !sky || landing;
      }
      const kind = classify(child.name);
      // Only animate the named object nodes, not glTF's per-primitive children.
      if (kind && child.parent && !classify(child.parent.name)) {
        counts[kind] = (counts[kind] ?? 0) + 1;
        list.push({ node: child, kind, i: counts[kind], base: { position: child.position.clone(), scale: child.scale.clone(), rotY: child.rotation.y } });
      }
    });
    return list;
  }, [scene]);

  useStudioReflections(scene, 0.8);
  // The landing's reeds reflect the landing itself, wet and glossy.
  useLandingReflections(scene, ['Reed'], 2);
  // Compile every shader and upload everything up front (with everything shown, so what appears later is included),
  // then report ready once a frame has drawn: no stalls mid-scroll when something first comes into view.
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera);
  const threeScene = useThree((s) => s.scene);
  useEffect(() => {
    let live = true;
    const hidden: Object3D[] = [];
    const hiddenMaterials: Material[] = [];
    const show = () =>
      threeScene.traverse((o) => {
        if (!o.visible) {
          o.visible = true;
          hidden.push(o);
        }
        const m = (o as Mesh).material;
        for (const material of Array.isArray(m) ? m : m ? [m] : []) {
          if (!material.visible) {
            material.visible = true;
            hiddenMaterials.push(material);
          }
        }
      });
    const restore = () => {
      for (const o of hidden) o.visible = false;
      for (const m of hiddenMaterials) m.visible = false;
    };
    show();
    // Never let the overlay hang on it: some browsers stall parallel shader compiles (e.g. in a background tab).
    const settle = new Promise((resolve) => setTimeout(resolve, 3000));
    // Textures still downloading (the scans and sky photo) are waited for, briefly, so they can be uploaded too.
    const textures = new Set<Texture>();
    threeScene.traverse((o) => {
      const m = (o as Mesh).material as (Material & Record<string, unknown>) | undefined;
      const uniforms = (m as unknown as { uniforms?: Record<string, { value: unknown }> })?.uniforms ?? {};
      for (const v of [...Object.values(m ?? {}), ...Object.values(uniforms).map((u) => u?.value)]) if ((v as Texture)?.isTexture) textures.add(v as Texture);
    });
    const loaded = Promise.all(
      [...textures].map(
        (t) =>
          new Promise<void>((resolve) => {
            const check = () => (t.image || !live ? resolve() : setTimeout(check, 50));
            check();
          })
      )
    );
    Promise.race([Promise.all([precompile(gl, threeScene, camera, threeScene), loaded]), settle])
      .catch(() => {})
      .then(() => {
        if (!live) return;
        // Draw everything once, off screen, from high above the canyon: every mesh, texture and shadow shader goes up
        // to the graphics card now rather than the first time it scrolls into view (a visible hitch mid-scroll).
        show();
        for (const t of textures) if (t.image) gl.initTexture(t);
        const target = new WebGLRenderTarget(64, 64);
        const overview = new PerspectiveCamera(100, 1, 0.1, 2000);
        overview.position.set(-40, 40, 0);
        overview.lookAt(0, -10, 0);
        overview.updateMatrixWorld();
        // (Every layer, so the rainbow's included.)
        overview.layers.enableAll();
        const previous = gl.getRenderTarget();
        gl.shadowMap.needsUpdate = true;
        gl.setRenderTarget(target);
        gl.render(threeScene, overview);
        // And the planter's materials as they'll be while it fades out.
        for (const m of toyMaterials) m.transparent = true;
        gl.render(threeScene, overview);
        for (const m of toyMaterials) m.transparent = false;
        gl.setRenderTarget(previous);
        target.dispose();
        // The prefiltering shaders the landing's reflection capture uses (components/three/landing-reflections.ts).
        // (Kept, not disposed: its programs are still compiling in the background, and they're shared by program cache.)
        new PMREMGenerator(gl).compileCubemapShader();
        restore();
        requestAnimationFrame(() => requestAnimationFrame(() => live && onReady()));
        // rAF doesn't run in a hidden tab; report anyway so it's ready when the tab comes back.
        setTimeout(() => live && onReady(), 600);
      });
    return () => {
      live = false;
      restore();
    };
  }, [gl, camera, threeScene, onReady, toyMaterials]);
  useEffect(() => {
    if (sun.current) onSun(sun.current);
  }, [onSun]);
  useEffect(() => {
    camera.layers.enable(RAINBOW_LAYER);
    camera.layers.enable(NO_MIRROR_LAYER);
  }, [camera]);

  useFrame((state, delta) => {
    const t = state.clock.elapsedTime;
    waterTime.value += Math.min(delta, 1 / 20);
    if (rainbow.current) {
      const bow = smoothstep(BEATS.bowIn, BEATS.bowFull, journey.frame);
      // Stronger for the landing shot, where it hangs bright in the fall's spray (as the reference's).
      rainbow.current.uniforms.uOpacity.value = bow * (1 + 0.9 * smoothstep(720, 765, journey.frame));
      rainbow.current.visible = false;
    }
    // The studio key gives way to the warm sun (components/three/sky.tsx) below the clouds.
    // The studio lights give way to the warm sun (components/three/sky.tsx): partly below the clouds, almost wholly at
    // the landing, where the light should be low, warm and contrasty.
    const landing = landingAt(journey.frame);
    // FogDrog's canyon world is still in the model but not this site's: the city (components/three/city.tsx) is.
    for (const o of below) o.visible = false;
    waterLedge.value = 0;
    // The ledge comes in gradually (it's too close to the camera for the haze to hide it).
    if (ledge) {
      const m = ledge.material as Material;
      m.opacity = ledgeIn(journey.frame);
      m.transparent = m.opacity < 0.999;
    }
    waterLanding.value = landing;
    // (The studio's flat light gives way as soon as the real sky comes in, not only at the landing.)
    const realLight = Math.max(0.75 * bloomAt(journey.frame), landing);
    // (Nearly gone at night: the studio's warm white sky would light every upward face in the city, the towers' spikes
    // glowing pale.)
    if (key.current) key.current.intensity = (1.8 - 0.7 * bloomAt(journey.frame)) * (1 - 0.95 * realLight);
    if (hemi.current) {
      // (In the cities, a soft fill from each one's sky and ground: lib/look.ts.)
      const dusk = look.day;
      hemi.current.intensity = 0.9 - 0.84 * realLight + look.hemi * dusk;
      hemi.current.color.lerpColors(STUDIO_SKY, look.hemiSky, dusk);
      hemi.current.groundColor.lerpColors(STUDIO_GROUND, look.hemiGround, dusk);
    }
    // The planter recedes into the haze above on the pull-back; its streams then pour out of the sky.
    const presence = toyPresence(journey.frame);
    for (const m of toyMaterials) {
      m.opacity = presence;
      m.transparent = presence < 0.999;
    }
    for (const o of toy) o.visible = presence > 0.001;
    waterFromSky.value = 1 - presence;
    for (const a of animated) {
      const { node, base, i } = a;
      switch (a.kind) {
        case 'ring':
          // MICRO • BIOME orbits slowly around the planter.
          node.rotation.y = base.rotY + t * 0.18;
          break;
        case 'cloud':
          node.position.x = base.position.x + Math.sin(t * 0.35 + i * 2.1) * 0.12;
          node.position.z = base.position.z + Math.cos(t * 0.25 + i) * 0.05;
          break;
        case 'star': {
          const s = 1 + Math.sin(t * 2.2 + i * 1.9) * 0.18;
          node.scale.copy(base.scale).multiplyScalar(s);
          node.rotation.y = base.rotY + Math.sin(t * 0.8 + i) * 0.4;
          break;
        }
        case 'letter':
          node.position.y = base.position.y + Math.sin(t * 1.6 - i * 0.7) * 0.035;
          break;
        case 'water':
          node.position.y = base.position.y + Math.sin(t * 0.9) * 0.004;
          break;
      }
    }
  });

  return (
    <>
      <hemisphereLight ref={hemi} args={['#fffaf2', '#e3d6c6', 0.9]} />
      <directionalLight
        ref={key}
        position={[-3, 6, 4]}
        intensity={1.8}
        color="#fff6ea"
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-bias={-0.0005}
        shadow-normalBias={0.03}
        shadow-camera-left={-2.5}
        shadow-camera-right={2.5}
        shadow-camera-top={3}
        shadow-camera-bottom={-1.5}
      />
      <primitive object={scene} />
      {/* The streams carried on down past the freeway into the city, as ropes of oil. */}
      <FallStreaks scene={scene} />
      {!devFlag('nospray') && <Spray scene={scene} />}
      <SilhouetteOutline target={scene} exclude={isOutsideOutline} depthAt={OUTLINE_DEPTH} fade={outlineFade} />
    </>
  );
}

// The sticker outline belongs to the hero; it lifts away as the camera opens up.
const outlineFade = () => 1 - smoothstep(10, 60, journey.frame);

if (typeof window !== 'undefined') useGLTF.preload(URL, DRACO_PATH);
