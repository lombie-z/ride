'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useMemo, useRef } from 'react';
import {
  BoxGeometry,
  CanvasTexture,
  CircleGeometry,
  Color,
  CylinderGeometry,
  DoubleSide,
  type Group,
  MeshBasicMaterial,
  MeshStandardMaterial,
  RingGeometry,
  ShaderMaterial,
  SRGBColorSpace,
  type Texture,
  TorusGeometry,
  Vector3,
} from 'three';
import { TRACE_LOOKS } from '@/components/trace-looks';
import { rhythm } from '@/lib/rhythm';
import { anchors, featureHere, ghostLocked, ride } from '@/lib/ride';
import { trace } from '@/lib/trace';

// The boost button: a pod bolted on beside the tank, a rocket on its face, from the chrome city on (the green city needs
// none: riding on is enough). What it does is each zone's (components/ride-button.tsx); its look follows: the chrome city's
// shimmers as it's held, the hive's beats with the heart, the desert's slides back along its rail as it's drawn, hot.

/** How far back it slides at full draw (m), and where it sits from the throttle's pill (along the bike, up, to its right). */
const TRAVEL = 0.055;
const OFFSET = [-0.015, 0.03, 0.19] as const;
/** Its tilt back toward the rider (radians). */
const TILT = 0.62;
const RADIUS = 0.058;

const COLOURS: Record<string, Color> = {
  surge: new Color('#a8f0ff'),
  heartbeat: new Color('#ffb02e'),
  slingshot: new Color('#ff7a2e'),
  start: new Color('#9dff7a'),
  ghost: new Color('#6dff7f'),
};
const HOT = new Color(1.0, 0.45, 0.12);
const DENIED = new Color(1.0, 0.1, 0.08);
const BOOSTED = new Color(1.0, 0.04, 0.05);
const colour = new Color();
const point = new Vector3();
const edge = new Vector3();

/** The rocket, nose up, on black. */
function rocketTexture() {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const g = canvas.getContext('2d') as CanvasRenderingContext2D;
  g.fillStyle = '#000';
  g.fillRect(0, 0, size, size);
  g.fillStyle = '#fff';
  // The body, a sharp nose down to a narrow tail.
  g.beginPath();
  g.moveTo(64, 8);
  g.bezierCurveTo(88, 30, 88, 62, 80, 88);
  g.lineTo(48, 88);
  g.bezierCurveTo(40, 62, 40, 30, 64, 8);
  g.fill();
  // The fins.
  g.beginPath();
  g.moveTo(45, 56);
  g.lineTo(22, 92);
  g.lineTo(47, 84);
  g.closePath();
  g.moveTo(83, 56);
  g.lineTo(106, 92);
  g.lineTo(81, 84);
  g.closePath();
  g.fill();
  // The flame.
  g.beginPath();
  g.moveTo(50, 94);
  g.lineTo(64, 124);
  g.lineTo(78, 94);
  g.closePath();
  g.fill();
  // The porthole.
  g.fillStyle = '#000';
  g.beginPath();
  g.arc(64, 44, 9, 0, Math.PI * 2);
  g.fill();
  const t = new CanvasTexture(canvas);
  t.colorSpace = SRGBColorSpace;
  return t;
}

/** The hive's button is an eye: open, half shut and shut, on black. */
function eyeTextures() {
  return [0.46, 0.2, 0.03].map((open) => {
    const size = 128;
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = size;
    const g = canvas.getContext('2d') as CanvasRenderingContext2D;
    g.fillStyle = '#000';
    g.fillRect(0, 0, size, size);
    const lid = 56 * open * 2;
    const almond = () => {
      g.beginPath();
      g.moveTo(8, 64);
      g.quadraticCurveTo(64, 64 - lid * 2, 120, 64);
      g.quadraticCurveTo(64, 64 + lid * 2, 8, 64);
      g.closePath();
    };
    almond();
    g.fillStyle = '#fff';
    g.fill();
    g.save();
    g.clip();
    g.fillStyle = '#b86a10';
    g.beginPath();
    g.arc(64, 64, 30, 0, Math.PI * 2);
    g.fill();
    g.fillStyle = '#000';
    g.beginPath();
    g.ellipse(64, 64, 9, 24, 0, 0, Math.PI * 2);
    g.fill();
    g.restore();
    almond();
    g.lineWidth = 6;
    g.strokeStyle = '#fff';
    g.stroke();
    const t = new CanvasTexture(canvas);
    t.colorSpace = SRGBColorSpace;
    return t;
  });
}

export function BoostPod({ env }: { env: Texture }) {
  const pod = useRef<Group>(null);
  const slider = useRef<Group>(null);
  const rail = useRef<Group>(null);
  const charge = useRef<Group>(null);
  const placed = useRef(false);
  const show = useRef(0);
  const parts = useMemo(() => {
    const body = new MeshStandardMaterial({ color: new Color(0.035, 0.035, 0.04), metalness: 0.85, roughness: 0.32, envMap: env, envMapIntensity: 1.2 });
    const rocket = rocketTexture();
    const eye = eyeTextures();
    const face = new MeshBasicMaterial({ map: rocket, toneMapped: false, side: DoubleSide });
    const rim = new MeshBasicMaterial({ toneMapped: false });
    const rail = new MeshBasicMaterial({ toneMapped: false });
    return {
      rocket,
      eye,
      body,
      face,
      rim,
      rail,
      plate: new BoxGeometry(0.235, 0.012, 0.15),
      mount: new BoxGeometry(0.13, 0.012, 0.13),
      arm: new CylinderGeometry(0.012, 0.012, 0.11, 8),
      drum: new CylinderGeometry(RADIUS * 1.08, RADIUS * 1.2, 0.03, 20),
      disc: new CircleGeometry(RADIUS, 24),
      ring: new TorusGeometry(RADIUS * 1.04, RADIUS * 0.12, 8, 28),
      groove: new BoxGeometry(0.21, 0.004, 0.008),
      // The ghost's recharge: an arc round the face, closing as it comes back.
      arc: new RingGeometry(RADIUS * 1.14, RADIUS * 1.42, 40),
      arcMaterial: new ShaderMaterial({
        uniforms: { uCharge: { value: 1 }, uColour: { value: new Color() } },
        transparent: true,
        depthWrite: false,
        toneMapped: false,
        side: DoubleSide,
        vertexShader: 'varying vec2 vP; void main() { vP = position.xy; gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }',
        fragmentShader: `uniform float uCharge; uniform vec3 uColour; varying vec2 vP;
          void main() {
            float a = fract(atan(vP.x, vP.y) / 6.28318);
            float on = step(a, uCharge);
            gl_FragColor = vec4(uColour * (0.12 + on), 0.25 + 0.75 * on);
          }`,
      }),
    };
  }, [env]);
  useEffect(
    () => () => {
      for (const v of Object.values(parts)) (v as { dispose?: () => void }).dispose?.();
      parts.rocket.dispose();
      for (const t of parts.eye) t.dispose();
    },
    [parts]
  );

  useFrame((state, delta) => {
    const g = pod.current;
    if (!g) return;
    // Beside the pill: in the bike's frame, once its button's found.
    const button = anchors.button;
    if (!placed.current && button && g.parent) {
      g.parent.updateWorldMatrix(true, false);
      button.getWorldPosition(point);
      g.parent.worldToLocal(point);
      g.position.set(point.x + OFFSET[0], point.y + OFFSET[1], point.z + OFFSET[2]);
      placed.current = true;
    }
    const feature = featureHere();
    const tr = ride.transition;
    // (It comes up with the zone's bike, and goes while pulled up: the arrival shot and the map want the bike alone.)
    // (And comes apart with the bike.)
    const wanted = ride.mounted && ride.mount > 0.9 && feature !== 'start' && !tr.arrived && ride.ghost.amount < 0.25 ? 1 : 0;
    show.current += (wanted - show.current) * Math.min(1, delta * 7);
    g.visible = show.current > 0.01;
    g.scale.setScalar(Math.max(0.001, show.current));
    const d = ride.drive;
    if (slider.current) slider.current.position.x = -TRAVEL * d.draw;
    const t = state.clock.elapsedTime;
    colour.copy(COLOURS[feature]);
    // How lit it is, by what it's doing.
    let light = 1.5 + 0.5 * Math.sin(t * 3);
    if (feature === 'surge') {
      // Held, it goes to the look's own colour.
      if (d.surge > 0.02) colour.lerp(new Color(TRACE_LOOKS[trace.look].accent), d.surge);
      light += 3.5 * d.surge;
    } else if (feature === 'heartbeat') {
      // Boosted, its eye's gone red with the ones round the view, going back to gold as it runs out.
      // (Held down in brightness as it does, or its iris and pupil would be lost in the red.)
      const red = Math.min(1, d.pump / 0.3);
      colour.lerp(BOOSTED, red);
      light = (1 + 1.3 * d.beat + 0.6 * d.pump) * (1 - 0.6 * red);
    } else if (feature === 'slingshot') {
      const heat = Math.max(d.draw, d.fire);
      colour.lerp(HOT, heat);
      light += 3 * d.draw + 3.5 * d.fire;
    } else if (feature === 'ghost') {
      // Spent, it's dark; recharging it comes up slowly; ready, it pulses.
      const { charge: c, state } = ride.ghost;
      light = state === 'ready' ? 2.2 + 1.3 * Math.sin(t * 5) : 0.2 + 0.7 * c;
      parts.arcMaterial.uniforms.uCharge.value = c;
      // Sealed through the gate and near the road's end: dark, flashing red if it's pressed.
      if (ghostLocked()) {
        light = 0.16;
        parts.arcMaterial.uniforms.uCharge.value = 0;
        colour.lerp(DENIED, ride.ghost.denied);
        light += 3 * ride.ghost.denied;
      }
      (parts.arcMaterial.uniforms.uColour.value as Color).copy(colour).multiplyScalar(state === 'ready' ? 1.6 + Math.sin(t * 5) * 0.6 : 2.4);
    }
    if (charge.current) charge.current.visible = feature === 'ghost';
    parts.face.color.copy(colour).multiplyScalar(light);
    // In the hive it's an eye, and it blinks when it's clicked (and now and then anyway).
    const b = rhythm.blink;
    const lids = b < 0.05 ? 1 : b < 0.15 ? 2 : b < 0.22 ? 1 : 0;
    const map = feature === 'heartbeat' ? parts.eye[lids] : parts.rocket;
    if (parts.face.map !== map) {
      parts.face.map = map;
      parts.face.needsUpdate = true;
    }
    parts.rim.color.copy(colour).multiplyScalar(0.8 + light * 0.6);
    if (rail.current) rail.current.visible = feature === 'slingshot';
    parts.rail.color.copy(colour).multiplyScalar(0.35 + 3.5 * d.draw);
    // Where it is on screen, for the button over it.
    const face = slider.current;
    const s = ride.boostScreen;
    s.shown = show.current > 0.7 && !!face;
    if (face && s.shown) {
      // (The camera's moved this frame, but its matrices only update when it renders.)
      state.camera.updateMatrixWorld();
      face.getWorldPosition(point).project(state.camera);
      s.x = (point.x * 0.5 + 0.5) * state.size.width;
      s.y = (-point.y * 0.5 + 0.5) * state.size.height;
      edge.set(RADIUS, 0, 0);
      face.localToWorld(edge).project(state.camera);
      s.r = Math.max(14, Math.hypot((edge.x * 0.5 + 0.5) * state.size.width - s.x, (-edge.y * 0.5 + 0.5) * state.size.height - s.y));
    }
  });

  // (Local +x along the bike, +y out of the plate. Its face is a plane turned up to +y.)
  return (
    <group ref={pod} visible={false} rotation={[0, 0, TILT]}>
      <mesh geometry={parts.mount} material={parts.body} position={[0, -0.012, 0]} />
      <mesh geometry={parts.arm} material={parts.body} position={[0, -0.022, -0.1]} rotation={[Math.PI / 2, 0, 0]} />
      {/* (Its rail, where it can be drawn back: the desert's.) */}
      <group ref={rail} visible={false}>
        <mesh geometry={parts.plate} material={parts.body} position={[-0.04, -0.012, 0]} />
        {[-0.052, 0.052].map((z) => (
          <mesh key={z} geometry={parts.groove} material={parts.rail} position={[-0.04, -0.003, z]} />
        ))}
      </group>
      <group ref={slider}>
        <mesh geometry={parts.drum} material={parts.body} position={[0, 0.008, 0]} />
        <mesh geometry={parts.ring} material={parts.rim} position={[0, 0.024, 0]} rotation={[-Math.PI / 2, 0, 0]} />
        <mesh geometry={parts.disc} material={parts.face} position={[0, 0.0245, 0]} rotation={[-Math.PI / 2, 0, -Math.PI / 2]} />
        <group ref={charge} visible={false}>
          <mesh geometry={parts.arc} material={parts.arcMaterial} position={[0, 0.0248, 0]} rotation={[-Math.PI / 2, 0, -Math.PI / 2]} />
        </group>
      </group>
    </group>
  );
}
