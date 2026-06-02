import { useState, useEffect, useCallback } from "react";
import { useLocation } from "react-router-dom";

const STORAGE_KEY = "inkforge_help_dismissed";

function getDismissedSet(): Set<string> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch { return new Set(); }
}

interface Props {
  children: React.ReactNode;
}

/** Persistent, dismissible inline help bar. Dismissed state is stored per-page in localStorage. */
export function PageHelp({ children }: Props) {
  const location = useLocation();
  const pageKey = location.pathname; // unique per route
  const [dismissed, setDismissed] = useState(() => getDismissedSet().has(pageKey));

  // Sync when route changes
  useEffect(() => {
    setDismissed(getDismissedSet().has(pageKey));
  }, [pageKey]);

  const close = useCallback(() => {
    const set = getDismissedSet();
    set.add(pageKey);
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...set]));
    setDismissed(true);
  }, [pageKey]);

  if (dismissed) return null;

  return (
    <div
      className="flex items-start gap-3 px-4 py-2.5 rounded-xl mb-4 text-sm animate-fade-in"
      style={{ background: "rgba(200,151,90,0.08)", border: "1px solid rgba(200,151,90,0.2)", color: "var(--text-2)" }}
    >
      <span className="mt-0.5 flex-shrink-0 text-base">💡</span>
      <span className="flex-1 leading-relaxed">{children}</span>
      <button
        onClick={close}
        className="flex-shrink-0 w-6 h-6 flex items-center justify-center rounded-md text-base leading-none transition-colors hover:opacity-70"
        style={{ color: "var(--text-3)" }}
        title="关闭提示"
      >×</button>
    </div>
  );
}

/** Clear all dismissed help hints so they show again. Call from a "?" button. */
export function resetAllHelps() {
  localStorage.removeItem(STORAGE_KEY);
  window.location.reload();
}

/** Check if any helps are currently dismissed. */
export function hasDismissedHelps(): boolean {
  return getDismissedSet().size > 0;
}
