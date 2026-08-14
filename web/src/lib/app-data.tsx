"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { callApi } from "@/lib/api";
import type {
  CatalogPayload,
  EventsPayload,
  PortfolioPayload,
  StatusPayload,
  ThesisPayload,
  WatchlistPayload,
} from "@/lib/types";

interface AppData {
  status: StatusPayload | null;
  events: EventsPayload | null;
  catalog: CatalogPayload | null;
  thesis: ThesisPayload | null;
  portfolio: PortfolioPayload | null;
  watchlist: WatchlistPayload | null;
  error: string | null;
  isLoading: boolean;
  refresh: () => Promise<void>;
  searchQuery: string;
  setSearchQuery: (q: string) => void;
}

const AppDataContext = createContext<AppData | null>(null);

// Tum sayfalarin ortak veri katmani. Eskiden Dashboard tek bir dev bilesende
// her seyi cekip active tab'a gore prop olarak dagitiyordu -- artik gercek
// route'lar var, her sayfa yalniz ihtiyaci olani buradan okuyor. Polling
// (15sn) ve ilk yukleme burada, sayfa degisiminde tekrar tetiklenmiyor.
export function AppDataProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<StatusPayload | null>(null);
  const [events, setEvents] = useState<EventsPayload | null>(null);
  const [catalog, setCatalog] = useState<CatalogPayload | null>(null);
  const [thesis, setThesis] = useState<ThesisPayload | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioPayload | null>(null);
  const [watchlist, setWatchlist] = useState<WatchlistPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const loadStatus = useCallback(async () => {
    try {
      setStatus(await callApi<StatusPayload>("/api/status"));
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Durum verisi yüklenemedi");
    }
  }, []);

  const refresh = useCallback(async () => {
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
    refresh();
    const interval = setInterval(loadStatus, 15000);
    return () => clearInterval(interval);
  }, [refresh, loadStatus]);

  return (
    <AppDataContext.Provider
      value={{
        status,
        events,
        catalog,
        thesis,
        portfolio,
        watchlist,
        error,
        isLoading,
        refresh,
        searchQuery,
        setSearchQuery,
      }}
    >
      {children}
    </AppDataContext.Provider>
  );
}

export function useAppData(): AppData {
  const ctx = useContext(AppDataContext);
  if (!ctx) throw new Error("useAppData must be used within AppDataProvider");
  return ctx;
}
