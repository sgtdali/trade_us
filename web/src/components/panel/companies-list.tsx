"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle, ChevronRight, Filter } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import type { Candidate, NextItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const BUCKET_CONFIG: Record<string, { badgeVariant: "default" | "secondary" | "outline" | "destructive"; className?: string }> = {
  A: { badgeVariant: "default", className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 font-bold" },
  B: { badgeVariant: "secondary", className: "bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30 font-bold" },
  C: { badgeVariant: "outline", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 font-bold" },
  Reject: { badgeVariant: "destructive", className: "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30 font-bold" },
};

const STATE_CONFIG: Record<string, { label: string; dot: string; text: string }> = {
  ready: { label: "Hazır", dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
  in_progress: { label: "İşlemde", dot: "bg-sky-500", text: "text-sky-600 dark:text-sky-400" },
  blocked: { label: "Engellendi", dot: "bg-rose-500", text: "text-rose-600 dark:text-rose-400" },
  waiting: { label: "Bekliyor", dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" },
  thesis_opened: { label: "Tez Açıldı", dot: "bg-indigo-500", text: "text-indigo-600 dark:text-indigo-400" },
  deprioritized: { label: "Önceliksiz", dot: "bg-slate-400", text: "text-muted-foreground" },
};

// Bu liste artik satiri tiklayinca inline genislemiyor -- her sirket kendi
// /companies/[ticker] sayfasina gidiyor. Tam gecmis, tetikleyiciler ve
// duzeltmeler orada, gercek bir sayfada; burasi yalniz filtrelenebilir bir
// index.
export function CompaniesList({
  status,
  searchQuery = "",
}: {
  status: { candidates: Candidate[]; next: NextItem[] } | null;
  searchQuery?: string;
}) {
  const [filterBucket, setFilterBucket] = useState<string>("ALL");
  const [filterState, setFilterState] = useState<string>("ALL");

  const nextByTicker = new Map((status?.next ?? []).map((item) => [item.ticker, item]));
  const candidatesList = status?.candidates ?? [];

  const filteredCandidates = candidatesList.filter((c) => {
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTicker = c.ticker.toLowerCase().includes(q);
      const matchSetup = c.setup?.toLowerCase().includes(q);
      const matchReason = c.status_reason?.toLowerCase().includes(q);
      if (!matchTicker && !matchSetup && !matchReason) return false;
    }
    if (filterBucket !== "ALL") {
      if (filterBucket === "NONE" && c.bucket !== null) return false;
      if (filterBucket !== "NONE" && c.bucket !== filterBucket) return false;
    }
    if (filterState !== "ALL" && c.state !== filterState) return false;
    return true;
  });

  // A once, sonra B/C/Reject/bucket-siz -- next_items()'in oncelik
  // sirasiyla ayni ilke, boylece "en cok dikkat isteyen" hep ustte.
  const BUCKET_PRIORITY: Record<string, number> = { A: 0, B: 1, C: 2, Reject: 3 };
  const sortedCandidates = [...filteredCandidates].sort((a, b) => {
    const pa = a.bucket ? BUCKET_PRIORITY[a.bucket] ?? 4 : 4;
    const pb = b.bucket ? BUCKET_PRIORITY[b.bucket] ?? 4 : 4;
    if (pa !== pb) return pa - pb;
    return a.ticker.localeCompare(b.ticker);
  });

  const isOverdue = (c: Candidate) =>
    c.triggers.some((t) => {
      const due = t.date ?? t.next_check_date;
      return due && new Date(due) <= new Date();
    });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg border border-border/80 bg-card/60">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 text-xs text-muted-foreground font-medium mr-1">
            <Filter className="h-3.5 w-3.5" />
            Filtrele:
          </div>
          <div className="flex items-center gap-1 bg-muted/40 p-0.5 rounded-md border border-border/60">
            {["ALL", "A", "B", "C", "Reject"].map((b) => (
              <button
                key={b}
                onClick={() => setFilterBucket(b)}
                className={cn(
                  "px-2 py-1 text-[11px] font-mono rounded transition-colors",
                  filterBucket === b
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {b === "ALL" ? "Tüm Bucket'lar" : b}
              </button>
            ))}
          </div>
          <select
            value={filterState}
            onChange={(e) => setFilterState(e.target.value)}
            className="h-7 rounded-md border border-border/60 bg-muted/40 px-2 text-xs font-medium focus:outline-none"
          >
            <option value="ALL">Tüm Durumlar</option>
            {Object.entries(STATE_CONFIG).map(([k, cfg]) => (
              <option key={k} value={k}>
                {cfg.label}
              </option>
            ))}
          </select>
        </div>
        <div className="text-xs font-mono text-muted-foreground">
          Gösterilen: <span className="font-bold text-foreground">{filteredCandidates.length}</span> / {candidatesList.length}
        </div>
      </div>

      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-28 font-bold">Ticker</TableHead>
              <TableHead className="w-28">Bucket</TableHead>
              <TableHead className="w-32">Durum</TableHead>
              <TableHead className="w-48">Sonraki Rota</TableHead>
              <TableHead>İnceleme Notu / Durum Açıklaması</TableHead>
              <TableHead className="w-8" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sortedCandidates.map((c) => {
              const nx = nextByTicker.get(c.ticker);
              const route = nx
                ? `${nx.workflow}${nx.workflow !== nx.requested_workflow ? ` → ${nx.requested_workflow}` : ""}`
                : (c.next_workflow ?? "-");
              const bucketCfg = c.bucket ? BUCKET_CONFIG[c.bucket] : null;
              const stateCfg = STATE_CONFIG[c.state] || { label: c.state, dot: "bg-slate-400", text: "" };
              const overdue = isOverdue(c);

              return (
                <TableRow key={c.ticker} className="hover:bg-muted/20 border-b border-border/40">
                  <TableCell className="font-bold font-mono text-sm p-0">
                    <Link href={`/companies/${c.ticker}`} className="flex items-center gap-1.5 px-4 py-2.5">
                      <span className="text-primary mr-0.5">$</span>
                      {c.ticker}
                      {overdue && (
                        <AlertTriangle
                          className="h-3.5 w-3.5 text-amber-500"
                          aria-label="Tetikleyici vadesi geçti"
                        />
                      )}
                    </Link>
                  </TableCell>
                  <TableCell>
                    {bucketCfg ? (
                      <Badge variant={bucketCfg.badgeVariant} className={bucketCfg.className}>
                        {c.bucket}
                      </Badge>
                    ) : (
                      <span className="text-muted-foreground font-mono">-</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1.5 text-xs font-medium">
                      <span className={cn("h-2 w-2 rounded-full", stateCfg.dot)} />
                      <span className={stateCfg.text}>{stateCfg.label}</span>
                      {overdue && (
                        <span className="text-[10px] text-amber-600 dark:text-amber-400 font-medium">
                          vadesi geçti
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="text-[10px] bg-background font-mono">
                      {route}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-md truncate">
                    {c.status_reason || "-"}
                  </TableCell>
                  <TableCell>
                    <Link href={`/companies/${c.ticker}`}>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </Link>
                  </TableCell>
                </TableRow>
              );
            })}
            {filteredCandidates.length === 0 && (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground">
                  Filtreye uygun aday bulunamadı.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
