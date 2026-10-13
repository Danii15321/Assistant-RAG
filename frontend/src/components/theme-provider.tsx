"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
export type Theme = "light" | "dark" | "system";
const ThemeContext = createContext<{ theme: Theme; selectTheme: (theme: Theme) => void } | null>(null);
export function ThemeProvider({ initialTheme, children }: { initialTheme: Theme; children: ReactNode }) {
  const [theme, setTheme] = useState(initialTheme);
  function selectTheme(next: Theme) {
    setTheme(next);
    document.documentElement.dataset.theme = next;
    // Appearance only: no identity, document or session data in this cookie.
    document.cookie = `mtr-theme=${next}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
  }
  return <ThemeContext.Provider value={{ theme, selectTheme }}>{children}</ThemeContext.Provider>;
}
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("ThemeProvider required");
  return context;
}
