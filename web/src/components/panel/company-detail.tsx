"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  FileText,
  ListTodo,
  ShieldAlert,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { callApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Candidate, NextItem, WorkflowEvent } from "@/lib/types";

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

// Bu alanlar baska yerde (Sonraki Adim karti, tetikleyiciler) zaten
// gosteriliyor -- bulgular bolumunde tekrar etmesin diye elenir.
const PAYLOAD_SKIP_KEYS = new Set(["workflow", "work_item_id", "promotion_evaluation"]);

function prettyLabel(key: string): string {
  return key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function PayloadValue({ value }: { value: unknown }) {
  if (value === null || value === undefined || value === "") return <span className="text-muted-foreground">-</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-muted-foreground">-</span>;
    return (
      <ul className="list-disc list-inside space-y-1">
        {value.map((v, i) => (
          <li key={i} className="text-xs text-foreground leading-relaxed">
            {typeof v === "object" ? JSON.stringify(v) : String(v)}
          </li>
        ))}
      </ul>
    );
  }
  if (typeof value === "object") {
    return (
      <div className="space-y-1 pl-3 border-l-2 border-border/60">
        {Object.entries(value as Record<string, unknown>).map(([k, v]) => (
          <div key={k} className="text-xs">
            <span className="text-muted-foreground">{prettyLabel(k)}: </span>
            <span className="text-foreground">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
          </div>
        ))}
      </div>
    );
  }
  return <span className="text-xs text-foreground leading-relaxed">{String(value)}</span>;
}

function PromotionEvaluationBadge({ evaluation }: { evaluation: Record<string, unknown> }) {
  const status = evaluation.resolution_status as string | undefined;
  const confidence = evaluation.confidence as number | undefined;
  if (!status) return null;
  return (
    <div className="flex items-center gap-2 text-xs p-2 rounded-md bg-muted/40 border border-border/50">
      <span className="font-semibold">Terfi değerlendirmesi:</span>
      <Badge variant={status === "resolved" ? "default" : "secondary"} className="font-mono text-[10px]">
        {status}
        {typeof confidence === "number" && ` (${Math.round(confidence * 100)}%)`}
      </Badge>
      {typeof evaluation.reason === "string" && <span className="text-muted-foreground">{evaluation.reason}</span>}
    </div>
  );
}

function ArtifactLink({ path, label }: { path: string; label: string }) {
  const [content, setContent] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    if (open) {
      setOpen(false);
      return;
    }
    if (!content) {
      setLoading(true);
      try {
        const data = await callApi<{ content: string }>(`/api/artifact?path=${encodeURIComponent(path)}`);
        setContent(data.content);
      } catch {
        setContent("(dosya okunamadı)");
      } finally {
        setLoading(false);
      }
    }
    setOpen(true);
  };

  return (
    <div>
      <button
        onClick={toggle}
        className="flex items-center gap-1.5 text-[11px] text-sky-600 dark:text-sky-400 hover:underline"
      >
        <FileText className="h-3 w-3" />
        {label}
        {loading ? "..." : open ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
      </button>
      {open && content && (
        <ScrollArea className="h-56 mt-2 rounded-md border border-border/80 bg-background/80 p-3">
          <pre className="font-mono text-xs text-foreground/90 whitespace-pre-wrap">{content}</pre>
        </ScrollArea>
      )}
    </div>
  );
}

// Idea-generation'in orijinal gerekcesi (setup/variant_wedge) her zaman
// ayni kalir -- gercek arastirma bulgulari (hedef fiyat, tez sutunlari, kill
// criteria, expectation bar...) tamamlanan her workflow'un kendi payload'inda
// yasar ve eskiden hic gosterilmiyordu. Bu bolum, o eksigi kapatir.
function ResearchHistory({ events }: { events: WorkflowEvent[] }) {
  const relevant = events
    .filter((e) => e.event_type === "workflow_completed" || e.event_type === "result_attached")
    .sort((a, b) => (a.recorded_at < b.recorded_at ? 1 : -1));

  if (relevant.length === 0) return null;

  return (
    <Card className="border-border/60 bg-card/60">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-semibold">Araştırma Bulguları</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {relevant.map((e) => {
          if (e.event_type === "result_attached") {
            const resultArtifact = e.source_artifacts.find((a) => a.role === "result");
            return (
              <div key={e.event_id} className="flex items-center justify-between p-2.5 rounded-md border border-border/50 bg-muted/20">
                <div className="flex items-center gap-2 text-xs">
                  <Badge variant="outline" className="text-[10px]">Sonuç Bağlandı</Badge>
                  <span className="font-mono text-[11px] text-muted-foreground">{e.recorded_at}</span>
                </div>
                {resultArtifact && <ArtifactLink path={resultArtifact.path} label="Ham analiz metnini gör" />}
              </div>
            );
          }

          const payload = e.payload;
          const workflow = typeof payload.workflow === "string" ? payload.workflow : null;
          const entries = Object.entries(payload).filter(
            ([k, v]) => !PAYLOAD_SKIP_KEYS.has(k) && v !== null && v !== undefined && v !== "",
          );
          const promotionEval = payload.promotion_evaluation as Record<string, unknown> | undefined;
          const resultArtifact = e.source_artifacts.find((a) => a.role === "result");

          return (
            <div key={e.event_id} className="rounded-lg border border-border/60 p-3.5 space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {workflow && (
                    <Badge variant="default" className="font-mono text-[11px]">
                      {workflow}
                    </Badge>
                  )}
                  <span className="font-mono text-[11px] text-muted-foreground">{e.recorded_at}</span>
                </div>
                {resultArtifact && <ArtifactLink path={resultArtifact.path} label="Kaynak analizi gör" />}
              </div>

              {promotionEval && <PromotionEvaluationBadge evaluation={promotionEval} />}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2.5">
                {entries.map(([key, value]) => (
                  <div key={key} className={Array.isArray(value) && value.length > 2 ? "sm:col-span-2" : ""}>
                    <div className="text-[11px] text-muted-foreground font-medium">{prettyLabel(key)}</div>
                    <div className="mt-0.5">
                      <PayloadValue value={value} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

export function CompanyDetail({
  ticker,
  candidate,
  queueItem,
  events,
}: {
  ticker: string;
  candidate: Candidate | null;
  queueItem: NextItem | null;
  events: WorkflowEvent[];
}) {
  if (!candidate) {
    return (
      <div className="space-y-4">
        <Link href="/companies" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
          <ArrowLeft className="h-3.5 w-3.5" /> Şirketlere dön
        </Link>
        <div className="p-8 text-center text-muted-foreground text-sm rounded-lg border border-border/60">
          <span className="font-mono font-bold">${ticker}</span> için kayıtlı bir aday bulunamadı.
        </div>
      </div>
    );
  }

  const bucketCfg = candidate.bucket ? BUCKET_CONFIG[candidate.bucket] : null;
  const stateCfg = STATE_CONFIG[candidate.state] || { label: candidate.state, dot: "bg-slate-400", text: "" };

  return (
    <div className="space-y-6">
      <Link href="/companies" className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground">
        <ArrowLeft className="h-3.5 w-3.5" /> Şirketlere dön
      </Link>

      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20 font-mono font-bold text-lg">
            ${candidate.ticker}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold font-mono">{candidate.ticker}</h1>
              {bucketCfg ? (
                <Badge variant={bucketCfg.badgeVariant} className={bucketCfg.className}>
                  Bucket {candidate.bucket}
                </Badge>
              ) : (
                <Badge variant="outline">Bucket yok</Badge>
              )}
            </div>
            <div className="flex items-center gap-1.5 text-xs font-medium mt-0.5">
              <span className={cn("h-2 w-2 rounded-full", stateCfg.dot)} />
              <span className={stateCfg.text}>{stateCfg.label}</span>
            </div>
          </div>
        </div>

        {queueItem && (
          <Link
            href="/queue"
            className="flex items-center gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 px-3.5 py-2 text-xs font-medium text-sky-600 dark:text-sky-400 hover:bg-sky-500/15 transition-colors"
          >
            <ListTodo className="h-4 w-4" />
            İş kuyruğunda aktif: <span className="font-mono font-semibold">{queueItem.workflow}</span>
            <ArrowLeft className="h-3.5 w-3.5 rotate-180" />
          </Link>
        )}
      </div>

      {/* Sonraki adım */}
      <Card className="border-border/60 bg-card/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold">Sonraki Adım</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div>
            <div className="text-[11px] text-muted-foreground">Sonraki Rota</div>
            <div className="font-mono text-xs font-semibold mt-1 text-primary">
              {candidate.next_workflow ?? "-"}
            </div>
          </div>
          <div>
            <div className="text-[11px] text-muted-foreground">İlk Tarama Önerisi (idea-generation, güncellenmez)</div>
            <div className="font-mono text-xs font-medium mt-1">{candidate.suggested_workflow ?? "-"}</div>
          </div>
          <div>
            <div className="text-[11px] text-muted-foreground">Manuel İnceleme Tarihi</div>
            <div className="font-mono text-xs mt-1">{candidate.manual_review_date ?? "-"}</div>
          </div>
          <div>
            <div className="text-[11px] text-muted-foreground">Son Olay Kaydı</div>
            <div className="font-mono text-[11px] mt-1 text-muted-foreground flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {candidate.last_event_at}
            </div>
          </div>
          {candidate.status_reason && (
            <div className="sm:col-span-2 lg:col-span-4 pt-2 border-t border-border/40 text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">Durum açıklaması: </span>
              {candidate.status_reason}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Gercek arastirma bulgulari -- hedef fiyat, tez sutunlari, kill
          criteria, expectation bar vb. Her tamamlanan workflow'un kendi
          payload'indan, genel bir alan render'iyla. */}
      <ResearchHistory events={events} />

      {/* Ilk tarama gerekcesi (idea-generation) */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="border-border/60 bg-card/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">
              Setup (ilk tarama)
            </CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-foreground font-medium leading-relaxed pt-0">
            {candidate.setup || "-"}
          </CardContent>
        </Card>
        <Card className="border-border/60 bg-card/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">Variant Wedge</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-foreground font-medium leading-relaxed pt-0">
            {candidate.variant_wedge || "-"}
          </CardContent>
        </Card>
        <Card className="border-border/60 bg-card/60">
          <CardHeader className="pb-2">
            <CardTitle className="text-[11px] font-semibold text-muted-foreground uppercase tracking-wider">First Rejection</CardTitle>
          </CardHeader>
          <CardContent className="text-xs text-foreground font-medium leading-relaxed pt-0">
            {candidate.first_rejection || "-"}
          </CardContent>
        </Card>
      </div>

      {/* Tamamlanan workflow'lar */}
      <Card className="border-border/60 bg-card/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold">Tamamlanan Workflow&apos;lar</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-1.5">
          {candidate.completed_workflows.length > 0 ? (
            candidate.completed_workflows.map((w) => (
              <Badge key={w} variant="secondary" className="font-mono text-[11px]">
                {w}
              </Badge>
            ))
          ) : (
            <span className="text-xs text-muted-foreground">Henüz tamamlanan workflow yok.</span>
          )}
        </CardContent>
      </Card>

      {/* Tetikleyiciler */}
      {candidate.triggers.length > 0 && (
        <Card className="border-border/60 bg-card/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              Tetikleyiciler
              <Badge variant="secondary" className="text-[10px]">{candidate.triggers.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <Table>
              <TableHeader className="bg-muted/40">
                <TableRow>
                  <TableHead className="h-8 text-[11px]">ID</TableHead>
                  <TableHead className="h-8 text-[11px]">Tip</TableHead>
                  <TableHead className="h-8 text-[11px]">Tarih / Sonraki Kontrol</TableHead>
                  <TableHead className="h-8 text-[11px]">Workflow</TableHead>
                  <TableHead className="h-8 text-[11px]">Tarih Durumu</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {candidate.triggers.map((t) => {
                  const dueDate = t.date ?? t.next_check_date;
                  const isOverdue = Boolean(dueDate && new Date(dueDate) <= new Date());
                  return (
                    <TableRow key={t.trigger_id} className="h-9 text-xs">
                      <TableCell className="font-mono text-[11px] font-medium">{t.trigger_id}</TableCell>
                      <TableCell>{t.type}</TableCell>
                      <TableCell className="font-mono text-[11px]">
                        <span className={isOverdue ? "text-amber-600 dark:text-amber-400 font-semibold" : ""}>
                          {dueDate ?? "-"}
                        </span>
                        {isOverdue && (
                          <span className="ml-1.5 text-[10px] text-amber-600 dark:text-amber-400">
                            (vadesi geldi)
                          </span>
                        )}
                      </TableCell>
                      <TableCell>
                        {t.workflow ? (
                          <Badge variant="outline" className="font-mono text-[10px]">{t.workflow}</Badge>
                        ) : (
                          "-"
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge variant={t.date_status === "confirmed" ? "default" : "secondary"} className="text-[10px]">
                          {t.date_status ?? "-"}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Düzeltmeler / terfi gecmisi */}
      {candidate.corrections.length > 0 && (
        <Card className="border-border/60 bg-card/60">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Düzeltmeler & Terfi Geçmişi</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {candidate.corrections.map((cor, i) => {
              const isPromotion = Boolean(cor.promoted_to);
              return (
                <div
                  key={i}
                  className={cn(
                    "rounded-lg border p-3 space-y-2",
                    isPromotion ? "border-emerald-500/30 bg-emerald-500/5" : "border-amber-500/30 bg-amber-500/5"
                  )}
                >
                  <div
                    className={cn(
                      "flex items-center gap-1.5 font-semibold text-xs",
                      isPromotion ? "text-emerald-500" : "text-amber-600 dark:text-amber-400"
                    )}
                  >
                    {isPromotion ? <CheckCircle2 className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />}
                    {isPromotion ? `Otomatik terfi: B → ${cor.promoted_to}` : "Rota düzeltmesi"}
                    {cor.resolution_status && (
                      <Badge variant="outline" className="ml-1 text-[10px] font-mono">
                        {cor.resolution_status}
                        {typeof cor.confidence === "number" && ` (${Math.round(cor.confidence * 100)}%)`}
                      </Badge>
                    )}
                  </div>
                  {cor.mapped_workflow && (
                    <div className="text-xs pl-5">
                      Yeni rota: <Badge variant="secondary" className="font-mono text-[10px]">{cor.mapped_workflow}</Badge>
                    </div>
                  )}
                  {cor.reason && <div className="text-xs font-medium text-foreground pl-5">{cor.reason}</div>}
                </div>
              );
            })}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
