'use client';

import { PerspectiveCamera } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import { PerspectiveCamera as Looker, MathUtils, type PerspectiveCamera as PerspectiveCameraImpl, Quaternion, Vector3 } from 'three';
import { course, type Shot } from '@/lib/course';
import { hallShown } from '@/lib/doors';
import { BEATS, heroStageSize, journey, journeyProgress, landingAt, PRE_ROLL, TRACK_FRAMES } from '@/lib/journey';
import { rhythm } from '@/lib/rhythm';
import { ARRIVAL, anchors, CRUISE, ride } from '@/lib/ride';
import { SECTION_TABLE, sectionAt, sections } from '@/lib/sections';

// The hero matches the blog's biome view (and the Blender preview camera): three-quarter, 3.7 units across the stage.
// A long lens from far away stands in for the blog's orthographic camera, so the journey can widen it.
const HERO_TARGET = new Vector3(0, 0.92, 0);
const HERO_DIRECTION = new Vector3(-1, 0.75, 1).normalize();
const HERO_FRAME = 3.7;
const HERO_FOV = 6;
// The fitted hero hands over to the authored track across its opening beat.
const OPEN_SHARE = BEATS.open / TRACK_FRAMES;
// The landing is composed at 16:9 (fitted to the concept, art/reference/concept-guides.json), the bike on the left. A
// narrower screen keeps the composition's left edge and loses its right (a lens shift, so nothing changes perspective);
// a tall phone also widens enough to keep the bike whole (this share of the composition, from its left), within reason.
const COMPOSED_ASPECT = 16 / 9;
const BIKE_SHARE = 0.6;
const MAX_LANDING_FOV = 75;
const tanHalf = (fov: number) => Math.tan(MathUtils.degToRad(fov / 2));

/** public/journey.json, exported from JourneyCam by art/export-journey.py: [x, y, z, qx, qy, qz, qw, fov] per frame. */
type Track = number[][];

const a = new Vector3();
const b = new Vector3();
const qa = new Quaternion();
const qb = new Quaternion();
const heroPosition = new Vector3();
const heroQuaternion = new Quaternion();
const trackPosition = new Vector3();
const trackQuaternion = new Quaternion();
const riderEye = new Vector3();
const riderAhead = new Vector3();
const riderQuaternion = new Quaternion();
// (A camera, so lookAt points its -z, the way it views.)
const looker = new Looker();
const forward = new Vector3(1, 0, 0);
// On the bike: the rider's view down the road, over the handlebars and the lit button.
// (Sat a little back from the model's RiderEye and looking a touch further down, so the dome and the lit button fill the
// bottom of the view, the road running away above them.)
const RIDER_FOV = 70;
const Y_AXIS = new Vector3(0, 1, 0);
const cityOrigin = new Vector3();
const arrivalEye = new Vector3();
const arrivalLook = new Vector3();
const RIDER_PITCH = MathUtils.degToRad(15);
const RIDER_BACK = 0.22;
const RIDER_DOWN = 0.07;
// Down the core's stairwell and tunnel (art/core/SECTIONS.md): a higher look and a wider lens, the stills' (at 15 degrees the top of the bulkhead's
// out of frame), and the view rigid on the bike, rolled with it. The flights' rattle: how far it shakes the eye (m) and the view (radians).
const SECTION_PITCH = MathUtils.degToRad(8);
const SECTION_FOV = 82;
const RATTLE = { eye: 0.02, view: 0.0045 };
const X_AXIS = new Vector3(1, 0, 0);
const Z_AXIS = new Vector3(0, 0, 1);
const riderUp = new Vector3();
const riderBack = new Vector3();
const bikeTurn = new Quaternion();
const viewTurn = new Quaternion();

/** Sample the track at progress p (0-1) into position/quaternion, returning the vertical FOV. */
function sample(track: Track, p: number, position: Vector3, quaternion: Quaternion) {
  const f = p * (track.length - 1);
  const i = Math.min(Math.floor(f), track.length - 2);
  const t = f - i;
  const [x0, y0, z0, ax, ay, az, aw, fov0] = track[i];
  const [x1, y1, z1, bx, by, bz, bw, fov1] = track[i + 1];
  position.copy(a.set(x0, y0, z0)).lerp(b.set(x1, y1, z1), t);
  quaternion.copy(qa.set(ax, ay, az, aw)).slerp(qb.set(bx, by, bz, bw), t);
  return fov0 + (fov1 - fov0) * t;
}

/** The camera the scroll runs along: the blog's hero framing at the top, then JourneyCam's authored path. */
export function JourneyCamera() {
  const camera = useRef<PerspectiveCameraImpl>(null);
  const track = useRef<Track | null>(null);

  useEffect(() => {
    let live = true;
    // Revalidate: the track changes whenever the path is re-cut in Blender.
    fetch('/journey.json', { cache: 'no-cache' })
      .then((r) => r.json())
      .then((data: { frames: Track }) => {
        if (live) track.current = data.frames;
      })
      // Without the track the hero simply stays.
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);

  // Before everything else each frame, so the rest reads this frame's journey position.
  useFrame((state) => {
    const cam = camera.current;
    if (!cam) return;
    const { width, height } = state.size;
    const aspect = width / height;

    // Hero: fit HERO_FRAME world units across the hero stage at the target's distance, whatever the viewport.
    const visibleHeight = (HERO_FRAME * height) / heroStageSize(width, height);
    const distance = visibleHeight / (2 * Math.tan(MathUtils.degToRad(HERO_FOV / 2)));
    heroPosition.copy(HERO_TARGET).addScaledVector(HERO_DIRECTION, distance);
    cam.position.copy(heroPosition);
    cam.lookAt(HERO_TARGET);
    heroQuaternion.copy(cam.quaternion);
    let fov = HERO_FOV;

    const frames = track.current;
    const scroll = journeyProgress();
    journey.sweep = Math.min(1, scroll / PRE_ROLL);
    const p = Math.max(0, (scroll - PRE_ROLL) / (1 - PRE_ROLL));
    journey.frame = p * TRACK_FRAMES;
    const landing = landingAt(journey.frame);
    let composed = 0;
    if (frames) {
      const trackFov = sample(frames, p, trackPosition, trackQuaternion);
      // Hand over from the fitted hero to the authored path across the opening beat.
      const w = MathUtils.smoothstep(p / OPEN_SHARE, 0, 1);
      cam.position.lerpVectors(heroPosition, trackPosition, w);
      cam.quaternion.slerpQuaternions(heroQuaternion, trackQuaternion, w);
      // The track is framed for landscape. On portrait screens widen it partway: enough to keep the shots readable,
      // not so far that the close passes turn fisheye.
      let fitted = aspect < 1 ? MathUtils.radToDeg(2 * Math.atan(tanHalf(trackFov) / Math.sqrt(aspect))) : trackFov;
      // At the landing, wide enough to hold the bike.
      const bikeFov = MathUtils.radToDeg(2 * Math.atan((tanHalf(trackFov) * COMPOSED_ASPECT * BIKE_SHARE) / aspect));
      fitted = MathUtils.lerp(fitted, Math.max(fitted, Math.min(bikeFov, MAX_LANDING_FOV)), landing);
      fov = MathUtils.lerp(HERO_FOV, fitted, w);
      // (The composition's half-width at unit distance.)
      composed = tanHalf(trackFov) * COMPOSED_ASPECT;
    }

    cam.fov = fov;
    // Slide the view so its left edge sits on the composition's: by the part of the composition it can't show, as a
    // share of its own width.
    const visible = tanHalf(fov) * aspect;
    const shift = (Math.max(0, composed - visible) / (2 * visible)) * landing;
    // (filmOffset moves the frustum by near * offset / film width; the view is 2 tan(fov / 2) * aspect near-units wide.)
    cam.filmOffset = -shift * 2 * tanHalf(fov) * aspect * cam.getFilmWidth();

    // Getting on the bike (components/three/ride.tsx eases ride.mount): glide from wherever the journey has the camera
    // to the rider's eye, looking along the bike, down the road.
    const eye = anchors.eye;
    if (eye && ride.mount > 0) {
      const e = ride.mount * ride.mount * ride.mount * (ride.mount * (ride.mount * 6 - 15) + 10);
      eye.getWorldPosition(riderEye);
      // (Forward along the bike: its own +x, from the node the eye hangs on.)
      riderAhead.copy(eye.position).add(forward);
      eye.parent?.localToWorld(riderAhead);
      riderAhead.sub(riderEye);
      riderBack.copy(riderAhead);
      riderAhead.setY(0).normalize();
      // (Through the stairwell and tunnel, back and down are the bike's own, however it's rolled; elsewhere the world's.)
      const { section, roll, rattle } = ride.drive;
      riderUp.copy(Y_AXIS);
      if (section > 0 && eye.parent) {
        riderUp
          .applyQuaternion(eye.parent.getWorldQuaternion(bikeTurn))
          .lerp(Y_AXIS, 1 - section)
          .normalize();
        riderBack.lerp(riderAhead, 1 - section).normalize();
      } else riderBack.copy(riderAhead);
      riderEye.addScaledVector(riderBack, -RIDER_BACK).addScaledVector(riderUp, -RIDER_DOWN);
      looker.position.copy(riderEye);
      looker.lookAt(
        riderAhead
          .multiplyScalar(10)
          .add(riderEye)
          // (Its nose up or down over the dunes, the view with it by half; all of it through the stairwell and tunnel.)
          .setY(riderEye.y + 10 * Math.tan(ride.drive.pitch * (0.5 + 0.5 * section)))
      );
      riderQuaternion.copy(looker.quaternion);
      const t = state.clock.elapsedTime;
      // (Rolled with the road, then looking a little down from the bike's own line: a wall ride really rolls the view.)
      if (section > 0) riderQuaternion.multiply(viewTurn.setFromAxisAngle(Z_AXIS, -roll * section + rattle * RATTLE.view * Math.sin(t * 83)));
      riderQuaternion.multiply(
        viewTurn.setFromAxisAngle(X_AXIS, -MathUtils.lerp(RIDER_PITCH, SECTION_PITCH, section) + rattle * RATTLE.view * Math.sin(t * 109))
      );
      // At speed: the view widens a little and the road buzzes up through the bars.
      const pace = Math.min(1, ride.drive.speed / CRUISE);
      // (Not off the ground, and not with the ride slowed to a stop; a landing's thump, though.)
      const buzz = pace * 0.006 * (ride.drive.air ? 0 : rhythm.slow) * (1 - ride.ghost.amount);
      riderEye.addScaledVector(riderUp, buzz * (Math.sin(t * 41) + 0.6 * Math.sin(t * 67)) - 0.16 * ride.drive.land);
      // (Down the flights' steps, it shakes through the bars.)
      riderEye.addScaledVector(riderUp, rattle * RATTLE.eye * (Math.sin(t * 97) + 0.7 * Math.sin(t * 151)));
      // (Riding the thing that runs in the bike's place: its gallop, up through the rider.)
      riderEye.addScaledVector(riderUp, ride.ghost.amount * 0.035 * Math.abs(Math.sin(t * 13)));
      cam.position.lerp(riderEye, e);
      cam.quaternion.slerp(riderQuaternion, e);
      // (Surging, the view stretches wider still; launched, it's punched wider again and shakes, and drawing the
      // throttle back it narrows, a breath held.)
      const { fire, draw } = ride.drive;
      cam.fov = MathUtils.lerp(
        cam.fov,
        MathUtils.lerp(RIDER_FOV + 12 * Math.min(1, pace * pace), SECTION_FOV, section) +
          10 * ride.drive.surge +
          14 * ride.drive.pump +
          20 * fire +
          6 * ride.ghost.amount -
          6 * draw,
        e
      );
      if (fire > 0.01) cam.position.y += fire * 0.012 * (Math.sin(t * 53) + 0.7 * Math.sin(t * 89));
      cam.filmOffset *= 1 - e;
    }
    // Pulled up in a city: the camera eases off the bike to its arrival shot.
    const tr = ride.transition;
    // (And when the map comes up, back onto the bike: the hands hold it up in the rider's view.)
    const shot = tr.arrive * (1 - MathUtils.smoothstep(tr.map, 0, 0.4));
    const leg = course.legs[ride.zone];
    if (tr.placed && shot > 0) {
      const a = shot * shot * shot * (shot * (shot * 6 - 15) + 10);
      const fitted: Shot = leg.shot ?? { eye: [...ARRIVAL.eye], look: [...ARRIVAL.look], fov: ARRIVAL.fov };
      cityOrigin.copy(leg.origin);
      arrivalEye
        .set(...fitted.eye)
        .applyAxisAngle(Y_AXIS, leg.yaw)
        .add(cityOrigin);
      arrivalLook
        .set(...fitted.look)
        .applyAxisAngle(Y_AXIS, leg.yaw)
        .add(cityOrigin);
      looker.position.copy(arrivalEye);
      looker.up.set(0, 1, 0);
      looker.lookAt(arrivalLook);
      cam.position.lerp(arrivalEye, a);
      cam.quaternion.slerp(looker.quaternion, a);
      cam.fov = MathUtils.lerp(cam.fov, fitted.fov, a);
    }
    // (Close in on the bike, the near plane has to be too, however far the ride has gone from the planter.)
    cam.near = ride.mount > 0 ? 0.04 : Math.max(0.03, cam.position.distanceTo(HERO_TARGET) * 0.002);
    // (Further once the cities are out there: their suns stand kilometres off, the desert's the furthest.)
    // (Indoors, in the core, nothing past its fog need be drawn: most of its 7 km is culled by this.)
    // (And less again down its stairwell and tunnel, lib/sections.ts: their fog's far closer.)
    // (Till the hall's in sight, through the bulkhead.)
    const inSection =
      ride.zone === 4 && tr.placed && !(ride.drive.s - tr.at > sections.flood.from && hallShown(ride.drive.s - tr.at)) ? sectionAt(ride.drive.s - tr.at) : null;
    cam.far = inSection
      ? SECTION_TABLE[inSection].far
      : ride.zone === 4 && tr.placed && ride.drive.s > tr.at + 41
        ? 1000
        : ride.zone === 3
          ? 9500
          : ride.transition.placed || ride.zone > 1
            ? 6000
            : 2000;
    cam.updateProjectionMatrix();
    if (process.env.NODE_ENV === 'development') (window as unknown as { __journeyCamera?: unknown }).__journeyCamera = cam;
  }, -1);

  return <PerspectiveCamera ref={camera} makeDefault />;
}
