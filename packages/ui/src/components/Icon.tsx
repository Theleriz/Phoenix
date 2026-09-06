/** Union of the icon sets duplicated in both apps' `main.tsx` before this rework. */
const PATHS: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z",
  chart: "M4 20V10m5 10V4m5 16v-7m5 7V7",
  message: "M4 5h16v11H8l-4 4z",
  play: "m9 6 8 6-8 6z",
  pause: "M8 5v14m8-14v14",
  sensor: "M12 3a9 9 0 0 1 0 18M12 7a5 5 0 0 1 0 10M4 12h.01",
  check: "m5 12 4 4L19 6",
  arrow: "m9 18 6-6-6-6",
  close: "M6 6l12 12M18 6 6 18",
  heart: "M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.9-8.6a5.5 5.5 0 0 0-.1-7.8",
  users: "M16 11a4 4 0 1 0-4-4M6 20v-1a4 4 0 0 1 4-4h1m3-6a4 4 0 1 1-4 4M14 20v-1a4 4 0 0 0-4-4",
  bell: "M18 8a6 6 0 1 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0",
};

export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
