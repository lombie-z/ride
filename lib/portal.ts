import { course } from './course';
import { ride } from './ride';

// The hive's holes: towers standing across its road, each with a lancet opening on the deck, where the road ends. The bike
// rides in, falls through the dark for a few seconds with eyes going past, and comes out of a hole high in another tower
// further along the road, falling onto it. As ride.ghost and lib/rhythm.ts: this is the state; components/three/portal.tsx
// draws it. drive.s holds at the black while it falls, then jumps on; its speed carries through.

export const PORTAL_ZONE = 2;

/** Each one: how far along the hive's road it's ridden into and the tower that's come out of stands (m), how long the fall (s). */
export const PORTALS = [
  { enter: 350, exit: 560, fall: 4.4 },
  { enter: 1395, exit: 1660, fall: 5.2 },
  { enter: 2810, exit: 3080, fall: 4.8 },
] as const;

/** The tower's axis stands this far past where the black is (art/build-portal.py BLACK_X). */
export const ENTRY_BLACK = 13;
/** Where it starts from coming out: this far past the tower's axis (in the dark passage), this high. Off the sill by a little. */
const EXIT_FROM = 5;
const EXIT_Y = 15;
/** How fast it's falling in the dark, and the least it comes out at, to clear the tower (m/s). */
const FALL_SPEED = 26;
const EXIT_SPEED = 30;
/** The tower it came out of goes once it's this far behind (m): nothing's looking back. */
const EXIT_GONE = 200;

export const portal = {
  /** The towers are in and drawn: until then, it's only road. */
  ready: false,
  state: 'road' as 'road' | 'fall',
  /** Which one it's in; seconds into the fall; how far it's gone in the dark (along the road, down). */
  i: -1,
  t: 0,
  along: 0,
  down: 0,
  /** drive.s last frame, to catch crossing the black however fast it's going. */
  last: 0,
  /** Which tower's been come out of and is still shown (-1 none). */
  exit: -1,
  /** How muffled the music is (0 to 1): as the core's ghost. */
  muffle: 0,
};

const hiveS = (u: number) => course.legs[PORTAL_ZONE].at + u;

function backOnRoad() {
  portal.state = 'road';
  portal.i = -1;
}

/** Each frame, after the ride's moved (step: the ride's own time, which stops when a boost is teaching; dt: real time). */
export function updatePortal(step: number, dt: number) {
  const p = portal;
  const d = ride.drive;
  const leg = course.legs[PORTAL_ZONE];
  const live = p.ready && ride.zone === PORTAL_ZONE && leg.placed && !!leg.in;
  p.muffle = p.state === 'fall' ? Math.min(1, p.muffle + dt * 3) : Math.max(0, p.muffle - dt * 1.2);
  if (p.state === 'fall') {
    const held = hiveS(PORTALS[p.i].enter);
    // (The wash has put everything back at the landing, under cover.)
    if (!live || d.s < held - 1) backOnRoad();
    // (Got off: it stays dark until the wash covers it.)
    else if (ride.mounted) {
      p.t += step;
      p.along += Math.min(d.speed, 60) * step;
      p.down += FALL_SPEED * step;
      d.s = held;
      d.y = 0;
      d.vy = -FALL_SPEED;
      d.air = true;
      if (p.t >= PORTALS[p.i].fall) {
        d.s = hiveS(PORTALS[p.i].exit + EXIT_FROM);
        d.y = EXIT_Y;
        d.vy = 0;
        d.speed = Math.max(d.speed, EXIT_SPEED);
        p.exit = p.i;
        backOnRoad();
      }
    }
  } else if (live && ride.mounted) {
    // (A jump along the road, as from the dev keys, isn't riding through anything.)
    const moved = d.s - p.last;
    if (moved > 0 && moved < Math.max(30, d.speed * 0.1)) {
      for (let i = 0; i < PORTALS.length; i++) {
        const at = hiveS(PORTALS[i].enter);
        if (p.last < at && d.s >= at) {
          d.s = at;
          Object.assign(p, { state: 'fall', i, t: 0, along: 0, down: 0 });
          break;
        }
      }
    }
  }
  if (p.exit >= 0 && (!live || d.s > hiveS(PORTALS[p.exit].exit + EXIT_GONE) || d.s < hiveS(PORTALS[p.exit].exit))) p.exit = -1;
  p.last = d.s;
}
