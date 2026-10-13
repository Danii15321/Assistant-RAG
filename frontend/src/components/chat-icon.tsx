import type { CSSProperties } from "react";

const paths = {
  compose: "M12 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-6M16 3l5 5-10 10-5 1 1-5L17 4M15 5l5 5",
  document: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6ZM14 2v6h6M8 13h8M8 17h6",
  chevron: "m9 5 7 7-7 7",
  settings: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM9 3h6l1 3 3 1 2 5-2 5-3 1-1 3H9l-1-3-3-1-2-5 2-5 3-1 1-3Z",
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1 1M18 18l1 1M5 19l1-1M18 6l1-1",
  moon: "M20 15.5A9 9 0 0 1 8.5 4 9 9 0 1 0 20 15.5Z",
  monitor: "M3 4h18v13H3zM8 21h8M12 17v4",
  shield: "M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Zm-4 9 3 3 5-6",
  plus: "M12 5v14M5 12h14",
  chat: "M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-1 1V11.5a8.5 8.5 0 0 1 17 0Z",
  library: "M4 4h5v16H4zM11 4h4v16h-4zM17 5l3-1 3 15-3 1z",
  arrow: "M12 19V5M5 12l7-7 7 7",
  menu: "M4 6h16M4 12h16M4 18h16",
  close: "m6 6 12 12M6 18 18 6",
  search: "M21 21l-5-5M18 10a8 8 0 1 1-16 0 8 8 0 0 1 16 0",
  trash: "M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7",
} as const;
export function ChatIcon({ name, style }: { name: keyof typeof paths; style?: CSSProperties }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={style}><path d={paths[name]} /></svg>;
}
