'use client';

import { useFrame } from '@react-three/fiber';
import { useEffect, useRef } from 'react';
import { course, groundAt, inLength, rollAt, ZONES } from '@/lib/course';
import { journey } from '@/lib/journey';
import { startMusic } from '@/lib/music';
import { BRAKE, bikeReady, MORPH_AFTER, ride, road, SETTLED_FRAME, startAt } from '@/lib/ride';
import { cruiseAt, sectionAt, sectionLook, sections } from '@/lib/sections';
import { AT } from './bike';

// `?at=chrome|hive|desert|core` starts on the bike at that zone's plaza; `&s=1300` at that far along its road, riding. For reviewing a
// place without riding there. Only that zone's city and bike are loaded (components/three/zone-city.tsx, bike.tsx): the ones before
// are marked as passed, with nothing to draw.

/** Where its frame's placed: anywhere clear of the green city (its street's not drawn past zone 1). */
const AWAY = 1000;

export function StartAt() {
  const stage = useRef<'scroll' | 'wait' | 'done'>('scroll');
  const settled = useRef(0);

  // (A browser won't play until it's been touched: the music starts on the first press, not getting on, as there's been none.)
  useEffect(() => {
    if (!startAt) return;
    window.addEventListener('pointerdown', startMusic, { once: true, capture: true });
    return () => window.removeEventListener('pointerdown', startMusic, { capture: true });
  }, []);

  useFrame(() => {
    if (!startAt || stage.current === 'done') return;
    const { k, s } = startAt;
    if (stage.current === 'scroll') {
      ride.zone = k;
      // (Only once the page has let go of the scroll and the smooth scrolling's taken it up: before then it's put back to the top.)
      if (document.documentElement.style.overflow === 'hidden') return;
      window.scrollTo(0, document.documentElement.scrollHeight);
      settled.current = journey.frame >= SETTLED_FRAME ? settled.current + 1 : 0;
      if (settled.current < 40) return;
      Object.assign(ride, { since: 10, appear: 1, activated: true, mounted: true, mount: 1, previewTime: 99 });
      stage.current = 'wait';
      return;
    }
    const leg = course.legs[k];
    if (!leg.ready || !leg.in || !bikeReady[k] || !road.known) return;
    // (Down the core's stairwell or tunnel: its own glb, once it's loaded: components/three/core-sections.tsx.)
    const inSection = k === 4 && s !== null ? sectionAt(s) : null;
    if (inSection && !sections.ready[inSection]) return;
    for (let j = 1; j < k; j++) Object.assign(course.legs[j], { placed: true, at: 0 });
    leg.at = AWAY;
    leg.origin.set(AT[0], AT[1], AT[2]).addScaledVector(road.ahead, leg.at);
    leg.yaw = road.yaw;
    leg.placed = true;
    const riding = s !== null;
    Object.assign(ride.transition, { placed: true, at: leg.at, t: 1, clear: 1, arrived: !riding, arrive: riding ? 0 : 1, held: 0, map: 0 });
    Object.assign(ride.morph, { from: k, to: k, at: 1 });
    Object.assign(ride.drive, {
      s: leg.at + (s ?? inLength(leg)),
      speed: riding ? (k === 4 ? cruiseAt(s as number, ZONES[k].cruise, BRAKE) : ZONES[k].cruise) : 0,
      cruise: riding,
      time: MORPH_AFTER,
    });
    // (On the road where it is: down a flight, up a wall. Parked in the core's plaza, as low as its hall's been sunk.)
    const y = groundAt(ride.drive.s);
    Object.assign(ride.drive, {
      y,
      vy: 0,
      air: false,
      pitch: 0,
      roll: inSection ? rollAt(ride.drive.s) : 0,
      section: k === 4 ? sectionLook(s ?? inLength(leg)) : 0,
    });
    stage.current = 'done';
  });

  return null;
}
