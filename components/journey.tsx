'use client';

import dynamic from 'next/dynamic';
import { useCallback, useEffect, useState } from 'react';
import { RhythmOverlay } from '@/components/rhythm-overlay';
import { RideButton } from '@/components/ride-button';
import { SmoothScroll } from '@/components/smooth-scroll';
import { Ticket } from '@/components/ticket';
import { TraceOverlay } from '@/components/trace-overlay';
import { cn } from '@/lib/utils';

// three.js and the model load in the browser after the page is up; the overlay holds the hero still until then.
const JourneyCanvas = dynamic(() => import('@/components/three/journey-canvas'), { ssr: false });

export function Journey() {
  const [ready, setReady] = useState(false);
  const [progress, setProgress] = useState(0);
  const onReady = useCallback(() => setReady(true), []);
  const onProgress = useCallback((p: number) => setProgress(p), []);

  // No scrolling until the journey is in (the camera would jump).
  useEffect(() => {
    document.documentElement.style.overflow = ready ? '' : 'hidden';
  }, [ready]);

  return (
    <>
      <JourneyCanvas onReady={onReady} onProgress={onProgress} />
      {ready && <SmoothScroll />}
      {ready && <Ticket />}
      {ready && <RhythmOverlay />}
      {ready && <TraceOverlay />}
      {ready && <RideButton />}
      {/* Loading: the hero as a Blender still (same box as the live hero, lib/journey.ts heroStageSize), with a hairline
          of progress; it all fades away once the model is in and its shaders are ready. */}
      <div
        className={cn(
          'fixed inset-0 z-20 grid place-items-center bg-plaster transition-opacity duration-700 ease-out',
          ready && 'pointer-events-none opacity-0'
        )}
        aria-hidden={ready}
      >
        {/* biome-ignore lint/performance/noImgElement: a fixed-size transparent still; next/image adds nothing here. */}
        <img src="/images/3d/micro-biome.webp" alt="" className="aspect-square w-[min(calc(min(640px,100vw)-48px),72svh)] object-contain" />
        <output className="absolute inset-x-0 bottom-8 flex flex-col items-center gap-3">
          <span className="text-xs uppercase tracking-[0.18em] text-muted">{progress < 100 ? 'Growing the biome' : 'Filling the falls'}</span>
          <span className="h-px w-32 overflow-hidden bg-ink/10">
            <span className="block h-full bg-ink/60 transition-[width] duration-300" style={{ width: `${progress < 100 ? progress * 0.85 : 100}%` }} />
          </span>
        </output>
      </div>
    </>
  );
}
