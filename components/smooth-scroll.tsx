'use client';

import { ReactLenis } from 'lenis/react';
import { useEffect, useState } from 'react';

// Lenis eases wheel scrolling so the camera glides between beats; off for reduced motion.
export function SmoothScroll() {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => setEnabled(!window.matchMedia('(prefers-reduced-motion: reduce)').matches), []);
  return enabled ? <ReactLenis root options={{ lerp: 0.1 }} /> : null;
}
