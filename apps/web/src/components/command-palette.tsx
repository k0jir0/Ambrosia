"use client";

import { useMemo, useState } from "react";
import { Command, Search } from "lucide-react";

type ActionItem = {
  id: string;
  label: string;
  hint: string;
  run: () => void;
};

export function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [query, setQuery] = useState("");

  function navigateTo(url: string) {
    window.location.assign(url);
  }

  const actions = useMemo<ActionItem[]>(() => {
    const value = query.trim().toUpperCase();
    const maybeTicker = /^[A-Z]{1,5}$/.test(value) ? value : null;

    const base: ActionItem[] = [
      { id: "new-review", label: "New Review", hint: "Open thesis intake", run: () => navigateTo("/review/new") },
      { id: "dashboard", label: "Dashboard", hint: "Go to command center", run: () => navigateTo("/") },
      { id: "history", label: "Decision History", hint: "Open archive", run: () => navigateTo("/history") },
      { id: "calibration", label: "Calibration", hint: "Open performance analytics", run: () => navigateTo("/calibration") }
    ];

    if (maybeTicker) {
      base.unshift({
        id: `ticker-${maybeTicker}`,
        label: `Open ${maybeTicker} intelligence`,
        hint: "Jump to /markets/:ticker",
        run: () => navigateTo(`/markets/${maybeTicker}`)
      });
    }

    if (value.includes(" VS ")) {
      const symbols = value
        .split(" VS ")
        .map((item) => item.trim())
        .filter((item) => /^[A-Z]{1,5}$/.test(item));
      if (symbols.length >= 2) {
        const [primary, ...peers] = symbols;
        base.unshift({
          id: `compare-${symbols.join("-")}`,
          label: `Compare ${symbols.join(" vs ")}`,
          hint: "Open compare mode",
          run: () => navigateTo(`/markets/${primary}?compare=${peers.join(",")}`)
        });
      }
    }

    return base.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()) || item.hint.toLowerCase().includes(query.toLowerCase()) || query.trim().length === 0);
  }, [query]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/50 p-4" onClick={onClose}>
      <div className="panel mx-auto mt-20 w-full max-w-2xl rounded-lg p-4" onClick={(event) => event.stopPropagation()}>
        <div className="mb-3 flex items-center gap-2 rounded-md border border-line bg-fog/70 px-3 py-2">
          <Search className="h-4 w-4 text-ink/60" />
          <input
            autoFocus
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search actions or type ticker (AAPL)"
            className="focus-ring w-full bg-transparent text-sm outline-none"
          />
          <span className="inline-flex items-center gap-1 rounded border border-line px-2 py-1 text-[11px] text-ink/60">
            <Command className="h-3 w-3" /> K
          </span>
        </div>

        <ul className="space-y-1">
          {actions.map((action) => (
            <li key={action.id}>
              <button
                type="button"
                className="focus-ring w-full rounded-md border border-line/70 px-3 py-2 text-left hover:bg-white/5"
                onClick={() => {
                  action.run();
                  onClose();
                }}
              >
                <p className="text-sm font-medium text-ink">{action.label}</p>
                <p className="text-xs text-ink/65">{action.hint}</p>
              </button>
            </li>
          ))}
          {actions.length === 0 ? <li className="rounded-md border border-line/70 px-3 py-4 text-sm text-ink/65">No matching actions.</li> : null}
        </ul>
      </div>
    </div>
  );
}
