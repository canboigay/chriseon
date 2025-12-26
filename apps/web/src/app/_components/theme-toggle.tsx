"use client";

import { useEffect, useMemo, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "chr-theme";

function applyTheme(theme: Theme) {
  const el = document.documentElement;
  if (theme === "system") {
    el.removeAttribute("data-theme");
    return;
  }
  el.setAttribute("data-theme", theme);
}

function readStoredTheme(): Theme | null {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // ignore
  }
  return null;
}

export function ThemeToggle() {
  // IMPORTANT: keep initial render deterministic to avoid hydration mismatch.
  const [theme, setTheme] = useState<Theme>("system");
  const [didInitFromStorage, setDidInitFromStorage] = useState(false);

  // Initialize from storage after mount (client-only).
  useEffect(() => {
    const stored = readStoredTheme();
    if (stored) setTheme(stored);
    setDidInitFromStorage(true);
  }, []);

  // Apply theme + persist (but don't clobber storage before we've read it).
  useEffect(() => {
    applyTheme(theme);

    if (!didInitFromStorage) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
      // ignore
    }
  }, [theme, didInitFromStorage]);

  const label = useMemo(() => {
    if (theme === "system") return "system";
    if (theme === "dark") return "dark";
    return "light";
  }, [theme]);

  function cycle() {
    const next: Theme = theme === "system" ? "light" : theme === "light" ? "dark" : "system";
    setTheme(next);
  }

  return (
    <button
      type="button"
      onClick={cycle}
      className="chr-button"
      style={{
        height: 34,
        padding: "0 10px",
        fontSize: "0.72rem",
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        opacity: 0.92,
      }}
      aria-label={`Theme: ${label}. Click to change.`}
      title={`Theme: ${label} (click to change)`}
    >
      {label}
    </button>
  );
}
