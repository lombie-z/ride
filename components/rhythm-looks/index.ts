import { bone } from './bone';
import { brand } from './brand';
import { classic } from './classic';
import { flesh } from './flesh';
import { ooze } from './ooze';
import type { RhythmLook } from './shared';

// The hive's run's looks: living flesh's the hive's own; the burning brand's kept for the boss (it's self-contained: see
// brand.ts); the rest are still up for comparing. `?rhythm=a|b|c|d`, `y` to cycle them in dev; `?rhythm=0` is the old one. To
// drop one: delete its file and its entry here.
export const RHYTHM_LOOKS: RhythmLook[] = [classic, flesh, ooze, bone, brand];

/** Which one's shown unless asked otherwise. */
export const DEFAULT_LOOK = 1;

/** Which one a `?rhythm=` asks for. */
export function lookFromParam(param: string | null) {
  const i = RHYTHM_LOOKS.findIndex((l) => l.id === param);
  return i < 0 ? DEFAULT_LOOK : i;
}
