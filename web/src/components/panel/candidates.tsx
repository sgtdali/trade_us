"use client";

import { Fragment, useState } from "react";
import {
  ArrowRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Filter,
  Layers,
  Search,
  ShieldAlert,
  Sparkles,
  TrendingUp,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Candidate, NextItem } from "@/lib/types";
import { cn } from "@/lib/utils";

const BUCKET_CONFIG: Record<string, { label: string; badgeVariant: "default" | "secondary" | "outline" | "destructive"; className?: string }> = {
  A: { label: "Bucket A", badgeVariant: "default", className: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30 font-bold" },
  B: { label: "Bucket B", badgeVariant: "secondary", className: "bg-sky-500/15 text-sky-600 dark:text-sky-400 border-sky-500/30 font-bold" },
  C: { label: "Bucket C", badgeVariant: "outline", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 font-bold" },
  Reject: { label: "Reject", badgeVariant: "destructive", className: "bg-rose-500/15 text-rose-600 dark:text-rose-400 border-rose-500/30 font-bold" },
};

const STATE_CONFIG: Record<string, { label: string; dot: string; text: string }> = {
  ready: { label: "Hazır", dot: "bg-emerald-500", text: "text-emerald-600 dark:text-emerald-400" },
  in_progress: { label: "İşlemde", dot: "bg-sky-500", text: "text-sky-600 dark:text-sky-400" },
  blocked: { label: "Engellendi", dot: "bg-rose-500", text: "text-rose-600 dark:text-rose-400" },
  waiting: { label: "Bekliyor", dot: "bg-amber-500", text: "text-amber-600 dark:text-amber-400" },
  thesis_opened: { label: "Tez Açıldı", dot: "bg-indigo-500", text: "text-indigo-600 dark:text-indigo-400" },
  deprioritized: { label: "Önceliksiz", dot: "bg-slate-400", text: "text-muted-foreground" },
};

function CandidateDetail({ c }: { c: Candidate }) {
  return (
    <div className="space-y-4 bg-muted/20 p-5 rounded-b-lg border-x border-b border-border/80 text-xs">
      <Tabs defaultValue="analysis" className="w-full">
        <TabsList className="bg-muted/50 border border-border/60 p-0.5 h-8">
          <TabsTrigger value="analysis" className="text-xs h-7">Analiz & Tez</TabsTrigger>
          <TabsTrigger value="workflows" className="text-xs h-7">Workflow Geçmişi</TabsTrigger>
          <TabsTrigger value="triggers" className="text-xs h-7 flex items-center gap-1">
            Tetikleyiciler
            {c.triggers.length > 0 && (
              <Badge variant="secondary" className="ml-1 px-1 text-[10px] h-4">
                {c.triggers.length}
              </Badge>
            )}
          </TabsTrigger>
          {c.corrections.length > 0 && (
            <TabsTrigger value="corrections" className="text-xs h-7 text-rose-500">
              Düzeltmeler ({c.corrections.length})
            </TabsTrigger>
          )}
        </TabsList>

        {/* Tab 1: Analysis */}
        <TabsContent value="analysis" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="rounded-lg border border-border/60 bg-card p-3.5 space-y-1">
              <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Setup</div>
              <div className="text-xs text-foreground font-medium leading-relaxed">{c.setup || "-"}</div>
            </div>
            <div className="rounded-lg border border-border/60 bg-card p-3.5 space-y-1">
              <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Variant Wedge</div>
              <div className="text-xs text-foreground font-medium leading-relaxed">{c.variant_wedge || "-"}</div>
            </div>
            <div className="rounded-lg border border-border/60 bg-card p-3.5 space-y-1">
              <div className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">First Rejection</div>
              <div className="text-xs text-foreground font-medium leading-relaxed">{c.first_rejection || "-"}</div>
            </div>
          </div>
        </TabsContent>

        {/* Tab 2: Workflows */}
        <TabsContent value="workflows" className="mt-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="rounded-lg border border-border/60 bg-card p-3">
              <div className="text-[11px] text-muted-foreground">Tamamlanan Workflow&apos;lar</div>
              <div className="flex flex-wrap gap-1 mt-2">
                {c.completed_workflows.length > 0 ? (
                  c.completed_workflows.map((w) => (
                    <Badge key={w} variant="secondary" className="font-mono text-[10px]">
                      {w}
                    </Badge>
                  ))
                ) : (
                  <span className="text-muted-foreground">-</span>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-border/60 bg-card p-3">
              <div className="text-[11px] text-muted-foreground">Önerilen Workflow</div>
              <div className="font-mono text-xs font-semibold mt-1 text-primary">
                {c.suggested_workflow ?? "-"}
              </div>
            </div>

            <div className="rounded-lg border border-border/60 bg-card p-3">
              <div className="text-[11px] text-muted-foreground">Manuel İnceleme Tarihi</div>
              <div className="font-mono text-xs mt-1 text-foreground">
                {c.manual_review_date ?? "-"}
              </div>
            </div>

            <div className="rounded-lg border border-border/60 bg-card p-3">
              <div className="text-[11px] text-muted-foreground">Son Olay Kaydı</div>
              <div className="font-mono text-[11px] mt-1 text-muted-foreground flex items-center gap-1">
                <Clock className="h-3 w-3" />
                {c.last_event_at}
              </div>
            </div>
          </div>
        </TabsContent>

        {/* Tab 3: Triggers */}
        <TabsContent value="triggers" className="mt-4">
          {c.triggers.length > 0 ? (
            <div className="rounded-lg border border-border/60 overflow-hidden">
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow>
                    <TableHead className="h-8 text-[11px]">ID</TableHead>
                    <TableHead className="h-8 text-[11px]">Tip</TableHead>
                    <TableHead className="h-8 text-[11px]">Tarih / Sonraki Kontrol</TableHead>
                    <TableHead className="h-8 text-[11px]">Workflow</TableHead>
                    <TableHead className="h-8 text-[11px]">Tetik Durumu</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {c.triggers.map((t) => (
                    <TableRow key={t.trigger_id} className="h-9 text-xs">
                      <TableCell className="font-mono text-[11px] font-medium">{t.trigger_id}</TableCell>
                      <TableCell>{t.type}</TableCell>
                      <TableCell className="font-mono text-[11px]">
                        {t.date ?? t.next_check_date ?? "-"}
                      </TableCell>
                      <TableCell>
                        {t.workflow ? (
                          <Badge variant="outline" className="font-mono text-[10px]">
                            {t.workflow}
                          </Badge>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={t.date_status === "due" ? "default" : "secondary"}
                          className="text-[10px]"
                        >
                          {t.date_status ?? "-"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          ) : (
            <div className="p-4 text-center text-muted-foreground text-xs rounded-lg border border-border/40">
              Bu aday için tanımlı aktif tetikleyici bulunmuyor.
            </div>
          )}
        </TabsContent>

        {/* Tab 4: Corrections */}
        {c.corrections.length > 0 && (
          <TabsContent value="corrections" className="mt-4 space-y-2">
            {c.corrections.map((cor, i) => (
              <div key={i} className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 space-y-2">
                <div className="flex items-center gap-1.5 text-rose-500 font-semibold text-xs">
                  <ShieldAlert className="h-3.5 w-3.5" />
                  Orijinal İddia:
                </div>
                <div className="text-xs font-mono text-muted-foreground pl-5">{cor.original_claim}</div>
                <Separator className="bg-rose-500/20" />
                <div className="flex items-center gap-1.5 text-emerald-500 font-semibold text-xs pt-1">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Düzeltme:
                </div>
                <div className="text-xs font-medium text-foreground pl-5">{cor.correction}</div>
              </div>
            ))}
          </TabsContent>
        )}
      </Tabs>
    </div>
  );
}

export function Candidates({
  status,
  searchQuery = "",
}: {
  status: { candidates: Candidate[]; next: NextItem[] } | null;
  searchQuery?: string;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filterBucket, setFilterBucket] = useState<string>("ALL");
  const [filterState, setFilterState] = useState<string>("ALL");

  const nextByTicker = new Map((status?.next ?? []).map((item) => [item.ticker, item]));

  const candidatesList = status?.candidates ?? [];

  const filteredCandidates = candidatesList.filter((c) => {
    // Global search query match
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      const matchTicker = c.ticker.toLowerCase().includes(q);
      const matchSetup = c.setup?.toLowerCase().includes(q);
      const matchReason = c.status_reason?.toLowerCase().includes(q);
      if (!matchTicker && !matchSetup && !matchReason) return false;
    }

    // Bucket filter match
    if (filterBucket !== "ALL") {
      if (filterBucket === "NONE" && c.bucket !== null) return false;
      if (filterBucket !== "NONE" && c.bucket !== filterBucket) return false;
    }

    // State filter match
    if (filterState !== "ALL" && c.state !== filterState) return false;

    return true;
  });

  return (
    <div className="space-y-4">
      {/* Filter & Toolbar Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-lg border border-border/80 bg-card/60">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1 text-xs text-muted-foreground font-medium mr-1">
            <Filter className="h-3.5 w-3.5" />
            Filtrele:
          </div>

          {/* Bucket Filter */}
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

          {/* State Filter Select */}
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

      {/* Main Table */}
      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow className="hover:bg-transparent">
              <TableHead className="w-10" />
              <TableHead className="w-28 font-bold">Ticker</TableHead>
              <TableHead className="w-28">Bucket</TableHead>
              <TableHead className="w-32">Durum</TableHead>
              <TableHead className="w-48">Sonraki Rota</TableHead>
              <TableHead>İnceleme Notu / Durum Açıklaması</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredCandidates.map((c) => {
              const nx = nextByTicker.get(c.ticker);
              const route = nx
                ? `${nx.workflow}${nx.workflow !== nx.requested_workflow ? ` → ${nx.requested_workflow}` : ""}`
                : (c.next_workflow ?? "-");
              const isOpen = expanded === c.ticker;
              const bucketCfg = c.bucket ? BUCKET_CONFIG[c.bucket] : null;
              const stateCfg = STATE_CONFIG[c.state] || { label: c.state, dot: "bg-slate-400", text: "" };

              return (
                <Fragment key={c.ticker}>
                  <TableRow
                    onClick={() => setExpanded(isOpen ? null : c.ticker)}
                    className={cn(
                      "cursor-pointer transition-colors border-b border-border/40",
                      isOpen ? "bg-muted/40 font-medium" : "hover:bg-muted/20"
                    )}
                  >
                    <TableCell className="text-center p-0 pl-3">
                      {isOpen ? (
                        <ChevronDown className="h-4 w-4 text-primary" />
                      ) : (
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      )}
                    </TableCell>
                    <TableCell className="font-bold font-mono text-sm">
                      <span className="text-primary mr-0.5">$</span>
                      {c.ticker}
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
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-xs font-mono">
                        <Badge variant="outline" className="text-[10px] bg-background">
                          {route}
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-md truncate">
                      {c.status_reason || "-"}
                    </TableCell>
                  </TableRow>
                  {isOpen && (
                    <TableRow className="hover:bg-transparent">
                      <TableCell colSpan={6} className="p-0 border-b border-border/80">
                        <CandidateDetail c={c} />
                      </TableCell>
                    </TableRow>
                  )}
                </Fragment>
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
