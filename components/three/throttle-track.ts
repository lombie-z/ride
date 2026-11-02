import { AdditiveBlending, BufferGeometry, Color, Float32BufferAttribute, Group, type Material, Mesh, type Object3D, ShaderMaterial } from 'three';

// The throttle as a slingshot: the pill on the tank slides back along a track toward the rider as it's drawn
// (ride.drive.draw), riding the curve of the tank, and the track's grooves light up where it's pulled back from, hotter
// the further it's drawn. Built on the bike's ButtonCentre empty (its local +x along the bike, +y out of the tank).

/** How far back the pill slides at full draw (m). */
export const TRAVEL = 0.09;
// (The pill is 24 cm long: its front end at rest is 12 cm ahead of its centre.)
const FRONT = 0.12;
const RAIL = 0.066;

/**
 * The tank's surface under the track, below the pill's face (m), at distances back along the bike from the button's
 * centre (sampled from art/bike.blend and art/bike2.blend by casting down onto them): on the centre line and under the
 * rails either side.
 */
type Profile = { d: number[]; centre: number[]; side: number[] };
const D = [-0.16, -0.12, -0.08, -0.04, 0, 0.04, 0.08, 0.12, 0.16, 0.2, 0.24];
export const BLACK_TANK: Profile = {
  d: D,
  centre: [-0.0218, -0.0138, -0.0092, -0.0071, -0.006, -0.007, -0.0098, -0.0137, -0.019, -0.0261, -0.0341],
  side: [-0.0325, -0.0235, -0.0162, -0.0166, -0.0156, -0.0166, -0.0195, -0.0234, -0.0288, -0.0362, -0.0445],
};
// (The chrome tank sits higher behind the pill and drops away to the dash ahead of it; its centre line is about 4 mm
// above the rails' where it could be sampled, clear of the pill.)
const CHROME_SIDE = [-0.05, -0.0375, -0.0236, -0.0157, -0.012, -0.0102, -0.0084, -0.0072, -0.0068, -0.0074, -0.0083];
export const CHROME_TANK: Profile = { d: D, centre: CHROME_SIDE.map((h) => h + 0.004), side: CHROME_SIDE };

function height(p: Profile, key: 'centre' | 'side', d: number) {
  const { d: ds } = p;
  const values = p[key];
  if (d <= ds[0]) return values[0];
  for (let i = 1; i < ds.length; i++) {
    if (d <= ds[i]) return values[i - 1] + ((values[i] - values[i - 1]) * (d - ds[i - 1])) / (ds[i] - ds[i - 1]);
  }
  return values[values.length - 1];
}

/** Three grooves along the tank, the centre line and a rail either side of the pill, each a thin ribbon on its surface. */
function trackGeometry(p: Profile) {
  const position: number[] = [];
  const along: number[] = [];
  const across: number[] = [];
  const index: number[] = [];
  const from = -0.135;
  const to = 0.25;
  const steps = 40;
  for (const [z, w, key] of [
    [-RAIL, 0.005, 'side'],
    [0, 0.004, 'centre'],
    [RAIL, 0.005, 'side'],
  ] as const) {
    const start = position.length / 3;
    for (let i = 0; i <= steps; i++) {
      const d = from + ((to - from) * i) / steps;
      const y = height(p, key, d) + 0.0012;
      for (const side of [-1, 1]) {
        position.push(-d, y, z + (side * w) / 2);
        along.push(d);
        across.push(side);
      }
    }
    for (let i = 0; i < steps; i++) {
      const a = start + i * 2;
      index.push(a, a + 2, a + 1, a + 1, a + 2, a + 3);
    }
  }
  const g = new BufferGeometry();
  g.setAttribute('position', new Float32BufferAttribute(position, 3));
  g.setAttribute('along', new Float32BufferAttribute(along, 1));
  g.setAttribute('across', new Float32BufferAttribute(across, 1));
  g.setIndex(index);
  return g;
}

function trackMaterial(colour: Color) {
  return new ShaderMaterial({
    uniforms: {
      uColour: { value: colour },
      uHot: { value: new Color(1.0, 0.42, 0.08) },
      uDraw: { value: 0 },
      uGlow: { value: 0 },
      uTime: { value: 0 },
    },
    vertexShader: /* glsl */ `
      attribute float along;
      attribute float across;
      varying float vAlong;
      varying float vAcross;
      void main() {
        vAlong = along;
        vAcross = across;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }`,
    fragmentShader: /* glsl */ `
      uniform vec3 uColour;
      uniform vec3 uHot;
      uniform float uDraw;
      uniform float uGlow;
      uniform float uTime;
      varying float vAlong;
      varying float vAcross;
      void main() {
        // Dim grooves, fading out at either end.
        float ends = smoothstep(-0.135, -0.11, vAlong) * (1.0 - smoothstep(0.19, 0.25, vAlong));
        float groove = 0.3 * ends;
        // Where the pill's been pulled back from (its front end at rest to where it is now), lit up like a drawn band,
        // with pulses running back along it.
        float front = -${FRONT.toFixed(3)} + ${TRAVEL.toFixed(3)} * uDraw;
        float band = step(-${FRONT.toFixed(3)} - 0.006, vAlong) * (1.0 - smoothstep(front - 0.004, front + 0.004, vAlong)) * step(0.01, uDraw);
        float pulse = 0.65 + 0.35 * sin(vAlong * 260.0 - uTime * 24.0);
        vec3 hot = mix(uColour, uHot, smoothstep(0.2, 1.0, uDraw));
        float soft = 1.0 - 0.6 * abs(vAcross);
        vec3 c = (uColour * groove + hot * band * (1.5 + 2.5 * uDraw) * pulse) * uGlow * soft;
        gl_FragColor = vec4(c, 1.0);
      }`,
    transparent: true,
    blending: AdditiveBlending,
    depthWrite: false,
    toneMapped: false,
  });
}

/**
 * Puts the bike's button (its meshes with these materials) on a slider over the track. Returns its update, given how far
 * it's drawn (0 to 1) and how brightly the track shows, and its teardown; null if the bike has no ButtonCentre.
 */
export function throttleTrack(scene: Object3D, materials: string[], colour: Color, profile: Profile) {
  const centre = scene.getObjectByName('ButtonCentre');
  if (!centre?.parent) return null;
  scene.updateMatrixWorld(true);
  const rail = new Group();
  rail.position.copy(centre.position);
  rail.quaternion.copy(centre.quaternion);
  rail.scale.copy(centre.scale);
  centre.parent.add(rail);
  rail.updateMatrixWorld(true);
  const slider = new Group();
  rail.add(slider);
  slider.updateMatrixWorld(true);
  const pill: Object3D[] = [];
  scene.traverse((o) => {
    const m = (o as Mesh).material as Material | undefined;
    if ((o as Mesh).isMesh && m && materials.includes(m.name)) pill.push(o);
  });
  const homes = pill.map((o) => o.parent);
  for (const o of pill) slider.attach(o);
  const material = trackMaterial(colour);
  const track = new Mesh(trackGeometry(profile), material);
  track.name = 'ThrottleTrack';
  track.frustumCulled = false;
  track.renderOrder = 2;
  rail.add(track);
  const h = (d: number) => height(profile, 'centre', d);
  // (The tank's slope back along the bike, so the pill tilts to sit on it.)
  const slope = (d: number) => (h(d + 0.01) - h(d - 0.01)) / 0.02;
  return {
    set(draw: number, glow: number, time: number) {
      const s = TRAVEL * draw;
      slider.position.set(-s, h(s) - h(0), 0);
      slider.rotation.z = Math.atan(-slope(s)) - Math.atan(-slope(0));
      material.uniforms.uDraw.value = draw;
      material.uniforms.uGlow.value = glow;
      material.uniforms.uTime.value = time;
      track.visible = glow > 0.002;
    },
    dispose() {
      pill.forEach((o, i) => {
        homes[i]?.attach(o);
      });
      rail.removeFromParent();
      track.geometry.dispose();
      material.dispose();
    },
  };
}
