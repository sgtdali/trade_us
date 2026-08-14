"use client";

import { Watchlist } from "@/components/panel/watchlist";
import { useAppData } from "@/lib/app-data";

export default function WatchlistPage() {
  const { watchlist, refresh, searchQuery } = useAppData();
  return <Watchlist watchlist={watchlist} onChanged={refresh} searchQuery={searchQuery} />;
}
