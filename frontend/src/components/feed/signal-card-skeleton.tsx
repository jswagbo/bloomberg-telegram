export function SignalCardSkeleton() {
  return (
    <div className="bg-terminal-card border border-terminal-border rounded-xl p-5 animate-pulse">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-terminal-border" />
          <div>
            <div className="h-5 w-24 bg-terminal-border rounded mb-2" />
            <div className="h-3 w-32 bg-terminal-border rounded" />
          </div>
        </div>
        <div className="h-8 w-16 bg-terminal-border rounded-lg" />
      </div>

      {/* Metrics */}
      <div className="grid grid-cols-4 gap-4 mb-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-4 bg-terminal-border rounded" />
        ))}
      </div>

      {/* Sentiment */}
      <div className="mb-4">
        <div className="h-3 w-20 bg-terminal-border rounded mb-2" />
        <div className="h-1.5 bg-terminal-border rounded-full" />
      </div>

      {/* Signal */}
      <div className="bg-terminal-bg rounded-lg p-3 mb-4">
        <div className="h-3 w-24 bg-terminal-border rounded mb-2" />
        <div className="h-4 w-full bg-terminal-border rounded" />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-3 border-t border-terminal-border">
        <div className="flex gap-2">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="h-6 w-16 bg-terminal-border rounded" />
          ))}
        </div>
        <div className="h-4 w-20 bg-terminal-border rounded" />
      </div>
    </div>
  );
}
