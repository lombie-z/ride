import { lockOn } from './lock-on';
import { mercury } from './mercury';
import { phosphor } from './phosphor';
import { scribe } from './scribe';
import type { TraceLook } from './shared';

// The chrome city's surge's looks, up for choosing: `?trace=a|b|c|d`, `t` to cycle them in dev. To drop one: delete its file
// and its entry here (mercury is the chrome city's; lock-on is kept for the final boss, whatever else goes).
export const TRACE_LOOKS: TraceLook[] = [mercury, lockOn, phosphor, scribe];

/** Which one's shown unless asked otherwise: mercury. */
export const DEFAULT_LOOK = 0;

/** Which one a `?trace=` asks for. */
export function lookFromParam(param: string | null) {
  const i = TRACE_LOOKS.findIndex((l) => l.id === param);
  return i < 0 ? Math.min(DEFAULT_LOOK, TRACE_LOOKS.length - 1) : i;
}

/** The looks' edge treatments for speed-blur.ts's shader, and which runs: `surgeLook` is the index of the one showing. */
export const surgeEdgeShader = /* glsl */ `
${TRACE_LOOKS.map((l) => l.edge).join('\n')}
vec3 surgeEdge(vec2 uv, vec2 toward, vec3 c) {
  if (surge <= 0.001) return c;
${TRACE_LOOKS.map((l, i) => `  if (surgeLook < ${i}.5) return edge${l.id.toUpperCase()}(uv, toward, c);`).join('\n')}
  return c;
}`;
