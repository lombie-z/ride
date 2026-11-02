'use client';

import { PerspectiveCamera } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import { MathUtils, type PerspectiveCamera as PerspectiveCameraImpl, Quaternion, Vector3 } from 'three';
import { BEATS, heroStageSize, journey, journeyProgress, landingAt, PRE_ROLL, TRACK_FRAMES } from '@/lib/journey';

// The hero matches the blog's biome view (and the Blender preview camera): three-quarter, 3.7 units across the stage.
// A long lens from far away stands in for the blog's orthographic camera, so the journey can widen it.
const HERO_TARGET = new Vector3(0, 0.92, 0);
const HERO_DIRECTION = new Vector3(-1, 0.75, 1).normalize();
const HERO_FRAME = 3.7;
const HERO_FOV = 6;
// The fitted hero hands over to the authored track across its opening beat.
const OPEN_SHARE = BEATS.open / TRACK_FRAMES;
// The landing is composed for landscape, its FogDrog sign and buttons on the left. A tall phone sees only the middle,
// so there the view slides left (a lens shift, so nothing changes perspective) by up to this share of its width.
const PORTRAIT_SHIFT = 0.24;

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
    if (frames) {
      const trackFov = sample(frames, p, trackPosition, trackQuaternion);
      // Hand over from the fitted hero to the authored path across the opening beat.
      const w = MathUtils.smoothstep(p / OPEN_SHARE, 0, 1);
      cam.position.lerpVectors(heroPosition, trackPosition, w);
      cam.quaternion.slerpQuaternions(heroQuaternion, trackQuaternion, w);
      // The track is framed for landscape. On portrait screens widen it partway: enough to keep the shots readable,
      // not so far that the close passes turn fisheye.
      const fitted = aspect < 1 ? MathUtils.radToDeg(2 * Math.atan(Math.tan(MathUtils.degToRad(trackFov / 2)) / Math.sqrt(aspect))) : trackFov;
      fov = MathUtils.lerp(HERO_FOV, fitted, w);
    }

    cam.fov = fov;
    const shift = PORTRAIT_SHIFT * MathUtils.clamp((1 - aspect) / 0.5, 0, 1) * landingAt(journey.frame);
    // (filmOffset moves the frustum by near * offset / film width; the view is 2 tan(fov / 2) * aspect near-units wide.)
    cam.filmOffset = -shift * 2 * Math.tan(MathUtils.degToRad(fov / 2)) * aspect * cam.getFilmWidth();
    cam.near = Math.max(0.03, cam.position.distanceTo(HERO_TARGET) * 0.002);
    cam.far = 2000;
    cam.updateProjectionMatrix();
    if (process.env.NODE_ENV === 'development') (window as unknown as { __journeyCamera?: unknown }).__journeyCamera = cam;
  }, -1);

  return <PerspectiveCamera ref={camera} makeDefault />;
}
