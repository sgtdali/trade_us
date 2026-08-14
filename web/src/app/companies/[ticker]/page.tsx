"use client";

import { useParams } from "next/navigation";
import { CompanyDetail } from "@/components/panel/company-detail";
import { useAppData } from "@/lib/app-data";

export default function CompanyDetailPage() {
  const params = useParams<{ ticker: string }>();
  const ticker = (params.ticker ?? "").toUpperCase();
  const { status } = useAppData();

  const candidate = status?.candidates.find((c) => c.ticker === ticker) ?? null;
  const queueItem = status?.next.find((n) => n.ticker === ticker) ?? null;

  return <CompanyDetail ticker={ticker} candidate={candidate} queueItem={queueItem} />;
}
