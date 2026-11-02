import { Journey } from '@/components/journey';

export default function Home() {
  return (
    <main>
      <h1 className="sr-only">Ride</h1>
      <Journey />
      {/* The scroll track the camera journey runs along. */}
      <div className="relative z-10 h-[600svh]" />
    </main>
  );
}
