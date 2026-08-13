"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { callApi } from "@/lib/api";
import type {
  CatalogPayload,
  EventsPayload,
  PortfolioPayload,
  StatusPayload,
  ThesisPayload,
  WatchlistPayload,
} from "@/lib/types";
import { Header, type NavId } from "@/components/header";
import { Overview } from "@/components/panel/overview";
import { IdeaRuns } from "@/components/panel/idea-runs";
import { Candidates } from "@/components/panel/candidates";
import { WorkQueue } from "@/components/panel/work-queue";
import { Portfolio } from "@/components/panel/portfolio";
import { Watchlist } from "@/components/panel/watchlist";
import { ThesisTracker } from "@/components/panel/thesis";
import { EventLog } from "@/components/panel/events";
import { Catalog } from "@/components/panel/catalog";

export function Dashboard() {
  const [active, setActive] = useState<NavId>("overview");
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [events, setEvents] = useState<EventsPayload | null>(null);
  const [catalog, setCatalog] = useState<CatalogPayload | null>(null);
  const [thesis, setThesis] = useState<ThesisPayload | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioPayload | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await callApi<StatusPayload>("/api/status"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Durum verisi yüklenemedi");
    }
  }, []);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        loadStatus(),
        callApi<EventsPayload>("/api/events?limit=200").then(setEvents).catch(() => undefined),
        callApi<CatalogPayload>("/api/catalog").then(setCatalog).catch(() => undefined),
        callApi<ThesisPayload>("/api/thesis").then(setThesis).catch(() => undefined),
        callApi<PortfolioPayload>("/api/portfolio").then(setPortfolio).catch(() => undefined),
        callApi<WatchlistPayload>("/api/watchlist").then(setWatchlist).catch(() => undefined),
      ]);
    } finally {
      setIsLoading(false);
    }
  }, [loadStatus]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial data fetch on mount
    loadAll();
    const interval = setInterval(loadStatus, 15000);
    return () => clearInterval(interval);
  }, [loadAll, loadStatus]);

  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      {/* Top Header */}
      <Header
        activeTab={active}
        onSelectTab={setActive}
        eventCount={status?.event_count}
        queueCount={status?.next.length}
        runsCount={status?.runs.length}
        portfolioCount={portfolio?.positions.length}
        watchlistCount={watchlist?.items.length}
        lastEventAt={status?.last_event_at}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onRefresh={loadAll}
        isLoading={isLoading}
      />

      {/* Main Workspace */}
      <main className="flex-1 min-w-0 p-4 sm:p-6 lg:p-8 max-w-7xl mx-auto w-full space-y-6">
        {error && (
          <div className="flex items-center gap-2 p-4 rounded-lg border border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400 text-xs font-medium">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>Sistem Hatası: {error}</span>
          </div>
        )}

        {active === "overview" && (
          <Overview status={status} onChanged={loadAll} searchQuery={searchQuery} />
        )}

        {active === "ideaRuns" && (
          <IdeaRuns runs={status?.runs ?? []} onChanged={loadAll} />
        )}

        {active === "candidates" && (
          <Candidates status={status} searchQuery={searchQuery} />
        )}

        {active === "queue" && (
          <WorkQueue items={status?.next ?? []} onChanged={loadAll} />
        )}

        {active === "portfolio" && (
          <Portfolio portfolio={portfolio} onChanged={loadAll} searchQuery={searchQuery} />
        )}

        {active === "watchlist" && (
          <Watchlist watchlist={watchlist} onChanged={loadAll} searchQuery={searchQuery} />
        )}

        {active === "thesis" && (
          <ThesisTracker theses={thesis?.theses ?? []} searchQuery={searchQuery} />
        )}

        {active === "events" && (
          <EventLog events={events?.events ?? []} searchQuery={searchQuery} />
        )}

        {active === "catalog" && (
          <Catalog catalog={catalog} />
        )}
      </main>
    </div>
  );
}
