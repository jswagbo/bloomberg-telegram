"use client";

import { useStore } from "@/lib/store";
import { cn } from "@/lib/utils";

const chains = [
  { id: null, label: "All Chains" },
  { id: "solana", label: "Solana" },
  { id: "base", label: "Base" },
  { id: "bsc", label: "BSC" },
];

const scoreFilters = [
  { min: 0, label: "All Scores" },
  { min: 50, label: "50+" },
  { min: 70, label: "70+ 🔥" },
  { min: 85, label: "85+ 🚀" },
];

const sourceFilters = [
  { min: 1, label: "1+ Source" },
  { min: 2, label: "2+ Sources" },
  { min: 3, label: "3+ Sources" },
  { min: 5, label: "5+ Sources" },
];

export function FeedFilters() {
  const { chain, minScore, minSources, setChain, setMinScore, setMinSources } = useStore();

  return (
    <div className="flex flex-wrap gap-4">
      {/* Chain Filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-terminal-muted">Chain:</span>
        <div className="flex gap-1 bg-terminal-card rounded-lg p-1">
          {chains.map((c) => (
            <button
              key={c.id || "all"}
              onClick={() => setChain(c.id)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                chain === c.id
                  ? "bg-primary-600 text-white"
                  : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-border"
              )}
            >
              {c.label}
            </button>
          ))}
        </div>
      </div>

      {/* Score Filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-terminal-muted">Score:</span>
        <div className="flex gap-1 bg-terminal-card rounded-lg p-1">
          {scoreFilters.map((s) => (
            <button
              key={s.min}
              onClick={() => setMinScore(s.min)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                minScore === s.min
                  ? "bg-primary-600 text-white"
                  : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-border"
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sources Filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-terminal-muted">Sources:</span>
        <div className="flex gap-1 bg-terminal-card rounded-lg p-1">
          {sourceFilters.map((s) => (
            <button
              key={s.min}
              onClick={() => setMinSources(s.min)}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                minSources === s.min
                  ? "bg-primary-600 text-white"
                  : "text-terminal-muted hover:text-terminal-text hover:bg-terminal-border"
              )}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
