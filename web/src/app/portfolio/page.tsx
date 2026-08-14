"use client";

import { Portfolio } from "@/components/panel/portfolio";
import { useAppData } from "@/lib/app-data";

export default function PortfolioPage() {
  const { portfolio, refresh, searchQuery } = useAppData();
  return <Portfolio portfolio={portfolio} onChanged={refresh} searchQuery={searchQuery} />;
}
