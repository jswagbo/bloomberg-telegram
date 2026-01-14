"use client";

import { SignalFeed } from "@/components/feed/signal-feed";
import { FeedFilters } from "@/components/feed/feed-filters";
import { FeedStats } from "@/components/feed/feed-stats";

export default function HomePage() {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <span className="text-fire">🔥</span> Signal Feed
          </h1>
          <p className="text-terminal-muted mt-1">
            Real-time intelligence from crypto Telegram channels
          </p>
        </div>
        <FeedStats />
      </div>

      {/* Filters */}
      <FeedFilters />

      {/* Main Feed */}
      <SignalFeed />
    </div>
  );
}
