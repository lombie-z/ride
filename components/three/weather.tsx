'use client';

import { useGLTF } from '@react-three/drei';
import { useFrame } from '@react-three/fiber';
import { useRef, useState } from 'react';
import type { Group } from 'three';
import { belowVisible, devFlag, isLightDevice, journey, landingAt, smoothstep } from '@/lib/journey';
import { look } from '@/lib/look';
import { pastFirstCity, ride } from '@/lib/ride';
import { DRACO_PATH } from './biome';
import { Mist } from './weather-mist';
import { Ooze } from './weather-ooze';
import { Rain } from './weather-rain';

/**
 * The landing's weather, as in the concept (art/reference/concept-green-city.webp): rain falling round the camera and
 * splashing on the deck, black ooze dripping off the gantry into its pool, and smog among the towers below. It all
 * comes in with the landing, so the hero and the descent are untouched. (?norain, ?noooze, ?nomist turn parts off.)
 */
export function Weather() {
  const { scene } = useGLTF('/models/city.glb', DRACO_PATH);
  const group = useRef<Group>(null);
  const [light] = useState(isLightDevice);
  // Each part's fade (0 to 1), written here and read in their own frame loops.
  const rain = useRef(0);
  const ooze = useRef(0);
  const mist = useRef(0);

  useFrame(() => {
    const f = journey.frame;
    const on = belowVisible(f) && landingAt(f) > 0;
    if (group.current) group.current.visible = on && !pastFirstCity();
    const landing = landingAt(f);
    // The rain starts as the camera comes down to the deck; the drips and the smog are there from the approach.
    // (The rain stops as the ride comes out of the smog into the second city's sunset.)
    rain.current = smoothstep(0.35, 1, landing) * (1 - smoothstep(0, 0.6, look.day));
    ooze.current = smoothstep(0.1, 0.5, landing);
    // (Thinner from the deck's new vantage, looking down on the city: at full strength it washed the towers out.)
    // (Its shells are centred on the landing: gone once the ride leaves it.)
    mist.current = 0.25 * landing * (1 - ride.drive.away);
  });

  return (
    <group ref={group} visible={false}>
      {!devFlag('nomist') && <Mist light={light} opacity={mist} />}
      {!devFlag('noooze') && <Ooze scene={scene} opacity={ooze} />}
      {!devFlag('norain') && <Rain light={light} opacity={rain} />}
    </group>
  );
}
