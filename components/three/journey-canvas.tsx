'use client';

import { PerformanceMonitor, SoftShadows, useProgress } from '@react-three/drei';
import { Canvas, useFrame } from '@react-three/fiber';
import { type RefObject, Suspense, useEffect, useRef, useState } from 'react';
import type { Mesh } from 'three';
import { BEATS, devFlag as flag, isLightDevice, journey, landingAt, pixelSize } from '@/lib/journey';
import { ride } from '@/lib/ride';
import { Bike } from './bike';
import { Biome } from './biome';
import { City } from './city';
import { CoreDoors } from './core-doors';
import { DriveStreet } from './drive';
import { Effects } from './effects';
import { HoloMap } from './holomap';
import { JourneyCamera } from './journey-camera';
import { PortalLoader } from './portal';
import { SectionFx } from './section-fx';
import { Sky } from './sky';
import { StartAt } from './start-at';
import { Weather } from './weather';
import { ZoneCityLoader } from './zone-city';

/** Download progress (0-100) of the model and decoder, for the loading overlay. */
function Progress({ onProgress }: { onProgress: (progress: number) => void }) {
  // (Subscribed outside React's render and passed on a tick later: the loader reports progress while the models'
  // components are rendering, and updating another component then is an error.)
  useEffect(() => {
    let live = true;
    const pass = (progress: number) => queueMicrotask(() => live && onProgress(progress));
    pass(useProgress.getState().progress);
    const stop = useProgress.subscribe((s) => pass(s.progress));
    return () => {
      live = false;
      stop();
    };
  }, [onProgress]);
  return null;
}

// Without the effect composer something still has to render (the outline pass's positive-priority frame callback
// turns off R3F's own rendering).
function Render() {
  useFrame(({ gl, scene, camera }) => gl.render(scene, camera), 1);
  return null;
}

/**
 * Shadows are the most expensive thing drawn (the sun's map covers the whole canyon), so they're redrawn only when
 * something they depend on has moved: while the camera's travelling (the lights follow the journey), and otherwise
 * every few frames for the swaying reeds and drifting toy.
 */
function ShadowBudget() {
  const last = { frame: -1, tick: 0 };
  useFrame(({ gl }) => {
    gl.shadowMap.autoUpdate = false;
    const moving = Math.abs(journey.frame - last.frame) > 0.05;
    last.frame = journey.frame;
    last.tick = (last.tick + 1) % 60;
    // The hero's toy idles (its letters bob), so its small map redraws often; on the way down nothing near the camera
    // casts a visible shadow, so a few times a second; at the landing everything in the sun's map stands still (the
    // bike parked, the drips cast none), so once a second; riding, the bike leaves the map behind, so never.
    const riding = ride.drive.s > 1 || ride.mount > 0.5;
    const every = journey.frame < BEATS.open ? 4 : landingAt(journey.frame) < 0.99 ? (moving ? 6 : 30) : 60;
    if (!riding && (last.tick % every === 0 || (moving && journey.frame < BEATS.open))) gl.shadowMap.needsUpdate = true;
  }, -2);
  return null;
}

/**
 * A resolution change reallocates every render buffer (a visible hitch), so it waits until the scroll has been still
 * for half a second.
 */
function ApplyWhenStill({ wanted, dpr, setDpr }: { wanted: RefObject<number>; dpr: number; setDpr: (dpr: number) => void }) {
  const still = useRef({ frame: -1, since: 0 });
  useFrame(({ clock }) => {
    const s = still.current;
    if (Math.abs(journey.frame - s.frame) > 0.01) {
      s.frame = journey.frame;
      s.since = clock.elapsedTime;
    }
    if (wanted.current !== dpr && clock.elapsedTime - s.since > 0.5) setDpr(wanted.current);
  });
  return null;
}

/** Dev: the renderer on window.__renderer, for measuring draw calls and frame cost. */
function Expose() {
  useFrame(({ gl }) => {
    (window as unknown as { __renderer?: unknown; __journeyFrame?: number }).__renderer = gl;
    (window as unknown as { __journeyFrame?: number }).__journeyFrame = journey.frame;
  });
  return null;
}

/**
 * Pixel mode's resolution switch: the full-resolution render while the hero's crisp and the sweep runs over it, the
 * low one (1/pixel) once the sweep covers the screen and looks the same; back when scrolling up into the hero.
 */
function PixelSwitch({ pixel, dpr, full, setDpr }: { pixel: number; dpr: number; full: number; setDpr: (dpr: number) => void }) {
  useFrame(() => {
    // (The map's panel is drawn in half the world's cell: twice the resolution while the hands are up, the world held at its
    // own by the sweep's effect, so it doesn't change.)
    const low = (ride.mapKeep.up ? 2 : 1) / pixel;
    if (dpr !== low && journey.sweep >= 0.999) setDpr(low);
    else if (dpr !== full && journey.sweep < 0.98) setDpr(full);
  });
  return null;
}

export default function JourneyCanvas({ onReady, onProgress }: { onReady: () => void; onProgress: (progress: number) => void }) {
  const [sun, setSun] = useState<Mesh | null>(null);
  const [light] = useState(isLightDevice);
  const [pixel] = useState(pixelSize);
  // Resolution adapts to the machine: down toward 1 while frames are slow, back up (to the cap) when there's room. (In
  // pixel mode the hero's drawn at this and everything after at 1/pixel; see PixelSwitch.)
  const maxDpr = light ? 1.5 : 1.75;
  const [dpr, setDpr] = useState(maxDpr);
  const wanted = useRef(maxDpr);
  return (
    <Canvas
      shadows={!flag('noshadow')}
      flat
      dpr={dpr}
      gl={{ antialias: false }}
      style={{ position: 'fixed', inset: 0, pointerEvents: 'none', zIndex: 1, imageRendering: dpr < 1 ? 'pixelated' : undefined }}
    >
      <PerformanceMonitor
        bounds={(refresh) => (refresh > 90 ? [50, 90] : [40, 58])}
        onChange={({ factor }) => {
          if (pixel) return;
          wanted.current = Math.round((1 + (maxDpr - 1) * factor) * 4) / 4;
        }}
      />
      {pixel ? <PixelSwitch pixel={pixel} dpr={dpr} full={maxDpr} setDpr={setDpr} /> : <ApplyWhenStill wanted={wanted} dpr={dpr} setDpr={setDpr} />}
      <ShadowBudget />
      {!flag('nosoft') && <SoftShadows size={42} samples={light ? 6 : 10} focus={0.35} />}
      <Progress onProgress={onProgress} />
      {process.env.NODE_ENV === 'development' && <Expose />}
      <JourneyCamera />
      <Sky sun={sun} />
      <Suspense fallback={null}>
        <Biome onReady={onReady} onSun={setSun} />
        {!flag('nocity') && <City />}
        {!flag('noweather') && <Weather />}
        {!flag('nobike') && <Bike />}
        {!flag('nodrive') && <DriveStreet />}
        <ZoneCityLoader k={1} />
        <ZoneCityLoader k={2} />
        <ZoneCityLoader k={3} />
        <ZoneCityLoader k={4} />
        <CoreDoors />
        <PortalLoader />
        <SectionFx />
        <HoloMap />
        <StartAt />
      </Suspense>
      {flag('nofx') ? <Render /> : <Effects sun={null} pixel={pixel} />}
    </Canvas>
  );
}
