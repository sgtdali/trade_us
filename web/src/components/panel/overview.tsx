"use client";

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Layers,
  ListTodo,
  RefreshCw,
  Search,
  Sparkles,
  TrendingUp,
  AlertCircle,
  ShieldCheck,
} from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { callApi } from "@/lib/api";
import type { StatusPayload } from "@/lib/types";

const BUCKET_CONFIG: Record<
  string,
  { label: string; bg: string; text: string; border: string; bar: string }
> = {
  A: {
    label: "Bucket A (Yüksek Öncelik)",
    bg: "bg-emerald-500/10",
    text: "text-emerald-600 dark:text-emerald-400",
    border: "border-emerald-500/30",
    bar: "bg-emerald-500",
  },
  B: {
    label: "Bucket B (Orta Öncelik)",
    bg: "bg-sky-500/10",
    text: "text-sky-600 dark:text-sky-400",
    border: "border-sky-500/30",
    bar: "bg-sky-500",
  },
  C: {
    label: "Bucket C (İzleme)",
    bg: "bg-amber-500/10",
    text: "text-amber-600 dark:text-amber-400",
    border: "border-amber-500/30",
    bar: "bg-amber-500",
  },
  Reject: {
    label: "Reject (Elenenler)",
    bg: "bg-rose-500/10",
    text: "text-rose-600 dark:text-rose-400",
    border: "border-rose-500/30",
    bar: "bg-rose-500",
  },
};

const STATE_CONFIG: Record<string, { label: string; color: string; dot: string }> = {
  ready: { label: "Hazır", color: "text-emerald-500", dot: "bg-emerald-500" },
  in_progress: { label: "İşlemde", color: "text-sky-500", dot: "bg-sky-500" },
  waiting: { label: "Bekliyor", color: "text-amber-500", dot: "bg-amber-500" },
  blocked: { label: "Engellendi", color: "text-rose-500", dot: "bg-rose-500" },
  thesis_opened: { label: "Tez Açıldı", color: "text-indigo-500", dot: "bg-indigo-500" },
  deprioritized: { label: "Önceliksiz", color: "text-muted-foreground", dot: "bg-slate-400" },
};

export function Overview({
  status,
  onChanged,
  searchQuery = "",
}: {
  status: StatusPayload | null;
  onChanged: () => void;
  searchQuery?: string;
}) {
  const [busy, setBusy] = useState(false);

  const bucketCounts: Record<string, number> = { A: 0, B: 0, C: 0, Reject: 0 };
  const stateCounts: Record<string, number> = {
    ready: 0,
    in_progress: 0,
    waiting: 0,
    blocked: 0,
    thesis_opened: 0,
    deprioritized: 0,
  };

  const totalCandidates = status?.candidates.length ?? 0;

  for (const c of status?.candidates ?? []) {
    if (c.bucket && c.bucket in bucketCounts) bucketCounts[c.bucket]++;
    if (c.state in stateCounts) stateCounts[c.state]++;
  }

  // Sirket sayfalarina dagilmis her tetikleyiciyi tek bir takvimde topla --
  // tek tek her /companies/[ticker]'a girmeden "sirada ne var, ne zaman"
  // gorulsun. Tarihe gore artan siralama: en yakin/geciken en ustte.
  const allTriggers = (status?.candidates ?? [])
    .flatMap((c) => c.triggers.map((t) => ({ ticker: c.ticker, trigger: t })))
    .map(({ ticker, trigger }) => {
      const dueDate = trigger.date ?? trigger.next_check_date ?? null;
      return {
        ticker,
        trigger,
        dueDate,
        overdue: Boolean(dueDate && new Date(dueDate) <= new Date()),
      };
    })
    .sort((a, b) => (a.dueDate ?? "9999").localeCompare(b.dueDate ?? "9999"));

  const runCheckTriggers = async (refresh: boolean) => {
    setBusy(true);
    try {
      const data = await callApi<{ additions: unknown[] }>("/api/check-triggers", { refresh });
      toast.success(`${data.additions.length} yeni tetikleyici olayı bulundu ve eklendi`);
      onChanged();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Tetikleyici kontrolü başarısız oldu");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Events Metric */}
        <Card className="relative overflow-hidden border-border/80 bg-card/60 backdrop-blur-xs shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Toplam Olaylar</CardTitle>
            <div className="rounded-md bg-primary/10 p-1.5 text-primary">
              <Activity className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight">
              {status?.event_count ?? "-"}
            </div>
            <div className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground font-mono">
              <Clock className="h-3 w-3" />
              <span>{status?.last_event_at ? status.last_event_at : "Henüz olay yok"}</span>
            </div>
          </CardContent>
        </Card>

        {/* Total Candidates Metric */}
        <Card className="relative overflow-hidden border-border/80 bg-card/60 backdrop-blur-xs shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Aktif Adaylar</CardTitle>
            <div className="rounded-md bg-emerald-500/10 p-1.5 text-emerald-500">
              <TrendingUp className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight">{totalCandidates}</div>
            <div className="mt-1 flex items-center gap-2 text-[11px]">
              <span className="text-emerald-500 font-semibold">{bucketCounts.A} Bucket A</span>
              <span className="text-muted-foreground">•</span>
              <span className="text-sky-500 font-semibold">{bucketCounts.B} Bucket B</span>
            </div>
          </CardContent>
        </Card>

        {/* Ready Work Items Metric */}
        <Card className="relative overflow-hidden border-border/80 bg-card/60 backdrop-blur-xs shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Kuyruktaki İşler</CardTitle>
            <div className="rounded-md bg-sky-500/10 p-1.5 text-sky-500">
              <ListTodo className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold font-mono tracking-tight">
              {status?.next.length ?? 0}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">
              {status?.next.length ? "İşlem yapılması bekleniyor" : "Kuyruk boş, bekleyen iş yok"}
            </div>
          </CardContent>
        </Card>

        {/* Pipeline Status Metric */}
        <Card className="relative overflow-hidden border-border/80 bg-card/60 backdrop-blur-xs shadow-xs">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xs font-medium text-muted-foreground">Motor Durumu</CardTitle>
            <div className="rounded-md bg-indigo-500/10 p-1.5 text-indigo-500">
              <ShieldCheck className="h-4 w-4" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-base font-semibold text-emerald-500">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-emerald-500"></span>
              </span>
              Aktif & Canlı
            </div>
            <div className="mt-1 text-[11px] font-mono text-muted-foreground">
              Otomatik senkronizasyon aktif (15s)
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Distribution Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Bucket Distribution */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span>Bucket Dağılımı</span>
              <Badge variant="outline" className="font-mono text-[10px]">
                {totalCandidates} hisse
              </Badge>
            </CardTitle>
            <CardDescription className="text-xs">
              Değerleme ve tez kalitesine göre aday grupları
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {Object.entries(BUCKET_CONFIG).map(([key, cfg]) => {
              const count = bucketCounts[key] || 0;
              const pct = totalCandidates > 0 ? Math.round((count / totalCandidates) * 100) : 0;
              return (
                <div key={key} className="space-y-1.5">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-medium flex items-center gap-2">
                      <span className={`inline-block h-2 w-2 rounded-full ${cfg.bar}`} />
                      {cfg.label}
                    </span>
                    <div className="font-mono text-xs flex items-center gap-2">
                      <span className="font-bold">{count}</span>
                      <span className="text-muted-foreground">({pct}%)</span>
                    </div>
                  </div>
                  <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
                    <div
                      className={`h-full transition-all duration-500 ${cfg.bar}`}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </CardContent>
        </Card>

        {/* State Distribution */}
        <Card className="border-border/80 bg-card/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span>Aday Durum Dağılımı</span>
              <Badge variant="outline" className="font-mono text-[10px]">
                Pipeline Aşamaları
              </Badge>
            </CardTitle>
            <CardDescription className="text-xs">
              İnceleme ve karar sürecindeki aşama sayıları
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {Object.entries(STATE_CONFIG).map(([key, cfg]) => {
                const count = stateCounts[key] || 0;
                return (
                  <div
                    key={key}
                    className="flex flex-col justify-between p-3 rounded-lg border border-border/60 bg-muted/20 hover:bg-muted/40 transition-colors"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-muted-foreground font-medium">{cfg.label}</span>
                      <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
                    </div>
                    <div className="mt-2 text-xl font-bold font-mono">{count}</div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Control Actions Hub */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Triggers Control Box */}
        <Card className="border-border/80 bg-card/60 lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Activity className="h-4 w-4 text-amber-500" />
              Tetikleyici & Veri Kontrolü
            </CardTitle>
            <CardDescription className="text-xs">
              Tarih, 10-K/10-Q bilanço açıklamaları ve olay bazlı tetikleyicileri denetleyin.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="p-3 rounded-md bg-muted/30 border border-border/60 text-xs text-muted-foreground space-y-1">
              <div className="flex items-center gap-1.5 font-medium text-foreground">
                <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                Otomatik Tetikleyici Motoru
              </div>
              <p className="text-[11px] leading-relaxed">
                Tetikleyici tarihleri gelen adaylar için otomatik olarak kuyruk işleri üretilir.
              </p>
            </div>

            <div className="flex flex-col gap-2 pt-1">
              <Button
                variant="secondary"
                onClick={() => runCheckTriggers(false)}
                disabled={busy}
                className="gap-1.5 text-xs"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} />
                Tetikleyicileri Kontrol Et
              </Button>
              <Button
                variant="outline"
                onClick={() => runCheckTriggers(true)}
                disabled={busy}
                className="gap-1.5 text-xs border-primary/30 text-primary hover:bg-primary/10"
              >
                <Sparkles className="h-3.5 w-3.5" />
                Veri ile Tazele & Kontrol Et
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Trigger Calendar -- her sirket sayfasina tek tek girmeden tum
            bekleyen tetikleyicileri tek yerde gorme */}
        <Card className="border-border/80 bg-card/60 lg:col-span-2">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Clock className="h-4 w-4 text-sky-500" />
                Tetikleyici Takvimi
              </span>
              {allTriggers.length > 0 && (
                <Badge variant="outline" className="font-mono text-[10px]">
                  {allTriggers.length} bekliyor
                </Badge>
              )}
            </CardTitle>
            <CardDescription className="text-xs">
              Tüm adaylardaki bekleyen tetikleyiciler, tarihe göre sıralı.
            </CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            {allTriggers.length > 0 ? (
              <Table>
                <TableHeader className="bg-muted/40">
                  <TableRow>
                    <TableHead className="h-8 text-[11px] w-24">Ticker</TableHead>
                    <TableHead className="h-8 text-[11px]">Tarih</TableHead>
                    <TableHead className="h-8 text-[11px]">Tip</TableHead>
                    <TableHead className="h-8 text-[11px]">Sonraki Workflow</TableHead>
                    <TableHead className="h-8 text-[11px]">Durum</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {allTriggers.map(({ ticker, trigger, dueDate, overdue }) => (
                    <TableRow key={trigger.trigger_id} className="h-9 text-xs">
                      <TableCell className="font-mono font-bold p-0">
                        <Link href={`/companies/${ticker}`} className="flex items-center gap-1 px-4 py-2 hover:underline">
                          {overdue && <AlertTriangle className="h-3 w-3 text-amber-500" />}
                          {ticker}
                        </Link>
                      </TableCell>
                      <TableCell className={`font-mono text-[11px] ${overdue ? "text-amber-600 dark:text-amber-400 font-semibold" : ""}`}>
                        {dueDate ?? "-"}
                        {overdue && <span className="ml-1.5 text-[10px]">(vadesi geçti)</span>}
                      </TableCell>
                      <TableCell className="text-[11px] text-muted-foreground">{trigger.type}</TableCell>
                      <TableCell>
                        {trigger.workflow ? (
                          <Badge variant="outline" className="font-mono text-[10px]">{trigger.workflow}</Badge>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={trigger.date_status === "confirmed" ? "default" : "secondary"} className="text-[10px]">
                          {trigger.date_status ?? "-"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            ) : (
              <div className="p-6 text-center text-xs text-muted-foreground">
                Bekleyen bir tetikleyici yok.
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
