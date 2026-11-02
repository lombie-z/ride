'use client';

import { useFrame } from '@react-three/fiber';
import { useMemo } from 'react';
import {
  BoxGeometry,
  type BufferGeometry,
  Color,
  CylinderGeometry,
  InstancedMesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  Object3D,
  type Texture,
  Vector3,
} from 'three';
import { mergeGeometries } from 'three/examples/jsm/utils/BufferGeometryUtils.js';
import { course } from '@/lib/course';
import { isLightDevice } from '@/lib/journey';
import { ride } from '@/lib/ride';

// Life in the second city: low-poly flying vehicles looping round its towers at different heights and speeds, and a
// monorail train on a beam beside the road in, coming up from behind and overtaking the bike as it nears the city.
// Drawn in the city's own frame (a child of its group; three's axes: x along the road in, y up, z to its right; the
// road in runs from its RoadIn at the origin back toward the green city along -x). Each is an instanced mesh, a
// handful of draw calls.

const PLAZA = new Vector3(560, 0, 160);
// The train: four cars on a beam beside the road in, 15 m to its right and 6 m up, from 700 m out to the city.
const BEAM = { from: -700, to: 260, side: 15, height: 6 };
const pearl = (env: Texture) =>
  new MeshStandardMaterial({ color: new Color(0.93, 0.9, 0.97), roughness: 0.28, metalness: 0.55, envMap: env, envMapIntensity: 1.3 });
const glow = (colour: Color) => new MeshBasicMaterial({ color: colour, toneMapped: false });

/** A flying car: a long six-sided hull, tapered to a nose, with stubby fins; its lights a band and a tail strip. */
function carGeometry() {
  const hull = new CylinderGeometry(0.55, 0.85, 4.6, 6).rotateZ(Math.PI / 2);
  const nose = new CylinderGeometry(0.0, 0.55, 1.4, 6).rotateZ(-Math.PI / 2).translate(3.0, 0, 0);
  const fins = new BoxGeometry(1.6, 0.12, 3.4).translate(-1.0, -0.1, 0);
  const fin = new BoxGeometry(1.0, 0.9, 0.1).translate(-2.0, 0.6, 0);
  return (mergeGeometries([hull, nose, fins, fin].map((g) => g.toNonIndexed())) as BufferGeometry).scale(3.2, 3.2, 3.2);
}
function carLightsGeometry() {
  const band = new BoxGeometry(2.4, 0.12, 1.74).translate(0.4, 0.25, 0);
  const tail = new BoxGeometry(0.1, 0.35, 1.5).translate(-2.32, 0, 0);
  return (mergeGeometries([band, tail].map((g) => g.toNonIndexed())) as BufferGeometry).scale(3.2, 3.2, 3.2);
}

type Flyer = { centre: Vector3; rx: number; rz: number; height: number; speed: number; phase: number; bob: number };

export function Traffic({ env }: { env: Texture }) {
  const light = isLightDevice();
  const flyers = useMemo<Flyer[]>(() => {
    const list: Flyer[] = [];
    const hash = (i: number, n: number) => {
      const h = Math.sin(i * 91.7 + n * 47.3) * 43758.5453;
      return h - Math.floor(h);
    };
    const count = light ? 14 : 28;
    for (let i = 0; i < count; i++) {
      const r = (n: number) => hash(i, n);
      list.push({
        // (Some over the city, some out over the water and the road in, where they're seen on the approach.)
        centre: new Vector3(i % 3 === 0 ? -150 + r(1) * 300 : PLAZA.x - 150 + r(1) * 300, 0, PLAZA.z - 200 + r(2) * 300),
        rx: 120 + r(3) * 380,
        rz: 90 + r(4) * 260,
        // (Low enough over the road and the water to be seen from the bike, a few up among the towers' tops.)
        height: 10 + r(5) ** 2 * 70,
        speed: (r(6) > 0.5 ? 1 : -1) * (14 + r(7) * 22),
        phase: r(8) * Math.PI * 2,
        bob: r(9) * 10,
      });
    }
    return list;
  }, [light]);

  const cars = useMemo(() => {
    const bodies = new InstancedMesh(carGeometry(), pearl(env), flyers.length);
    const lights = new InstancedMesh(carLightsGeometry(), glow(new Color(0.9, 2.6, 2.9)), flyers.length);
    for (const m of [bodies, lights]) m.frustumCulled = false;
    bodies.name = 'TrafficCars';
    lights.name = 'TrafficLights';
    return { bodies, lights };
  }, [env, flyers.length]);

  const train = useMemo(() => {
    const car = new BoxGeometry(15, 2.8, 3.2);
    const nose = new CylinderGeometry(0.2, 1.6, 4, 6)
      .rotateZ(-Math.PI / 2)
      .translate(9.4, -0.2, 0)
      .scale(1, 0.85, 1);
    const front = mergeGeometries([car.clone().toNonIndexed(), nose.toNonIndexed()]) as BufferGeometry;
    const cars = new InstancedMesh(car, pearl(env), 3);
    const lead = new InstancedMesh(front, pearl(env), 1);
    const windows = new InstancedMesh(new BoxGeometry(13.4, 0.7, 3.3).translate(0, 0.4, 0), glow(new Color(1.2, 1.5, 1.7)), 4);
    const beam = new InstancedMesh(new BoxGeometry(1, 1, 1), pearl(env), 1);
    for (const m of [cars, lead, windows, beam]) m.frustumCulled = false;
    return { cars, lead, windows, beam };
  }, [env]);

  const o = useMemo(() => new Object3D(), []);
  useFrame((state) => {
    if (!course.legs[1].placed) return;
    const t = state.clock.elapsedTime;
    flyers.forEach((f, i) => {
      const a = f.phase + (t * f.speed) / Math.max(f.rx, f.rz);
      const x = f.centre.x + Math.cos(a) * f.rx;
      const z = f.centre.z + Math.sin(a) * f.rz;
      // Heading along the loop: the derivative of the ellipse, banked a little into the turn.
      const dir = Math.sign(f.speed);
      o.position.set(x, f.height + Math.sin(t * 0.4 + f.bob) * 3, z);
      // (Its nose, local +x, along the velocity: dx = -sin a * rx, dz = cos a * rz, times the direction.)
      const vx = -Math.sin(a) * f.rx * dir;
      const vz = Math.cos(a) * f.rz * dir;
      o.rotation.set(0.15 * dir, Math.atan2(-vz, vx), 0, 'YXZ');
      o.updateMatrix();
      cars.bodies.setMatrixAt(i, o.matrix);
      cars.lights.setMatrixAt(i, o.matrix);
    });
    cars.bodies.instanceMatrix.needsUpdate = cars.lights.instanceMatrix.needsUpdate = true;

    // The beam rises out of the haze below as the towers there sink (ride.transition.clear), and the train on it.
    const clear = ride.transition.clear;
    const rise = clear * clear * (3 - 2 * clear);
    const lift = (1 - rise) * -70;
    o.position.set((BEAM.from + BEAM.to) / 2, BEAM.height - 2 + lift, BEAM.side);
    o.rotation.set(0, 0, 0);
    o.scale.set(BEAM.to - BEAM.from, 1.2, 1.6);
    o.updateMatrix();
    train.beam.setMatrixAt(0, o.matrix);
    train.beam.instanceMatrix.needsUpdate = true;
    o.scale.set(1, 1, 1);
    // The train: abreast of the bike while it's still a way out, then pulling ahead of it, until the beam ends.
    const u = ride.drive.s - course.legs[1].at;
    // (From 40 m behind the bike to 150 m ahead of it over the approach.)
    const lead = Math.min(BEAM.to - 8, Math.max(BEAM.from + 70, u - 40 + Math.max(0, Math.min(1, (u + 600) / 720)) * 190));
    for (let k = 0; k < 4; k++) {
      o.position.set(lead - k * 15.6, BEAM.height + lift, BEAM.side);
      o.rotation.set(0, 0, 0);
      o.updateMatrix();
      if (k === 0) train.lead.setMatrixAt(0, o.matrix);
      else train.cars.setMatrixAt(k - 1, o.matrix);
      train.windows.setMatrixAt(k, o.matrix);
    }
    for (const m of [train.lead, train.cars, train.windows]) m.instanceMatrix.needsUpdate = true;
  });

  return (
    <>
      <primitive object={cars.bodies} />
      <primitive object={cars.lights} />
      <primitive object={train.beam} />
      <primitive object={train.lead} />
      <primitive object={train.cars} />
      <primitive object={train.windows} />
    </>
  );
}
