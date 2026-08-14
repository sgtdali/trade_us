"use client";

import { useCallback, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Copy,
  FileCode,
  FileDown,
  FileText,
  Play,
  RefreshCw,
  Send,
  Sparkles,
  Terminal,
  XCircle,
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
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { callApi } from "@/lib/api";
import { useAppData } from "@/lib/app-data";
import { cn } from "@/lib/utils";
import type { NextItem, ValidationReport } from "@/lib/types";

const MODEL_LABEL: Record<string, string> = {
  "gpt-5.6-sol": "Sol",
  "gpt-5.6-terra": "Terra",
  "gpt-5.6-luna": "Luna",
};

function useSkillBadge(workflow: string) {
  const { catalog } = useAppData();
  const def = catalog?.workflows[workflow];
  if (!def?.codex_model) return null;
  const model = MODEL_LABEL[def.codex_model] ?? def.codex_model;
  return { model, effort: def.codex_effort ?? "-" };
}

function SkillBadge({ workflow }: { workflow: string }) {
  const badge = useSkillBadge(workflow);
  if (!badge) return null;
  return (
    <Badge variant="outline" className="font-mono text-[10px] gap-1 border-violet-500/30 text-violet-600 dark:text-violet-400">
      <Terminal className="h-2.5 w-2.5" />
      {badge.model} · {badge.effort}
    </Badge>
  );
}

export function WorkItemDetail({ item, onDone }: { item: NextItem; onDone: () => void }) {
  const [refresh, setRefresh] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [artifactDir, setArtifactDir] = useState<string | null>(item.artifact_dir ?? null);
  const [artifactContent, setArtifactContent] = useState<string | null>(null);
  const [activeArtifactFile, setActiveArtifactFile] = useState<string | null>(null);
  const [showArtifacts, setShowArtifacts] = useState(false);
  const [resultText, setResultText] = useState("");
  const [showManualPaste, setShowManualPaste] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [showRawDraft, setShowRawDraft] = useState(false);
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [codexRunning, setCodexRunning] = useState(false);
  const skillBadge = useSkillBadge(item.workflow);
  const isScreeningRun = item.workflow === "idea";

  const viewArtifact = useCallback(async (relPath: string) => {
    try {
      const data = await callApi<{ content: string }>(
        `/api/artifact?path=${encodeURIComponent(relPath)}`,
      );
      setArtifactContent(data.content);
      setActiveArtifactFile(relPath.split("/").pop() ?? relPath);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Artifact okunamadı");
    }
  }, []);

  const runPrepare = useCallback(async () => {
    if (!item.work_item_id) return;
    setPreparing(true);
    setArtifactContent(null);
    try {
      const data = await callApi<{ artifact_dir: string }>("/api/prepare", {
        work_item_id: item.work_item_id,
        no_refresh: !refresh,
      });
      setArtifactDir(data.artifact_dir);
      toast.success(`${item.ticker}: Veri paketi başarıyla hazırlandı`);
      onDone();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Prepare komutu başarısız oldu");
    } finally {
      setPreparing(false);
    }
  }, [item, refresh, onDone]);

  const runGenerateDraft = useCallback(async () => {
    setBusy(true);
    try {
      const data = await callApi<{ draft_json: string }>("/api/generate-draft", {
        run_id: item.run_id,
        work_item_id: item.work_item_id,
      });
      setDraftText(data.draft_json);
      toast.success("Taslak üretildi — onaylamadan önce gözden geçirin");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Taslak üretilemedi");
    } finally {
      setBusy(false);
    }
  }, [item]);

  const runCodexAuto = useCallback(async () => {
    setCodexRunning(true);
    try {
      const data = await callApi<{ result_path: string }>("/api/run-codex", {
        run_id: item.run_id,
        work_item_id: item.work_item_id,
      });
      toast.success(`Codex analizi tamamlandı: ${data.result_path}`);
      const content = await callApi<{ content: string }>(
        `/api/artifact?path=${encodeURIComponent(data.result_path)}`,
      );
      setResultText(content.content);
      try {
        const draftRes = await callApi<{ draft_json: string }>("/api/generate-draft", {
          run_id: item.run_id,
          work_item_id: item.work_item_id,
        });
        setDraftText(draftRes.draft_json);
        toast.success("Taslak dolduruldu — onaylamadan önce gözden geçirin");
      } catch {
        // non-blocking
      }
      onDone();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Codex çalıştırılamadı");
    } finally {
      setCodexRunning(false);
    }
  }, [item, onDone]);

  const submitAttach = useCallback(async () => {
    if (!resultText.trim()) {
      toast.error("Yapıştırılan analiz sonucu boş olamaz");
      return;
    }
    setBusy(true);
    try {
      const data = await callApi<{ result_path: string }>("/api/attach-result", {
        run_id: item.run_id,
        work_item_id: item.work_item_id,
        text: resultText,
      });
      toast.success(`Sonuç başarıyla bağlandı: ${data.result_path}`);
      try {
        const draftRes = await callApi<{ draft_json: string }>("/api/generate-draft", {
          run_id: item.run_id,
          work_item_id: item.work_item_id,
        });
        setDraftText(draftRes.draft_json);
        toast.success("Taslak dolduruldu — onaylamadan önce gözden geçirin");
      } catch {
        // non-blocking
      }
      onDone();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "attach-result başarısız");
    } finally {
      setBusy(false);
    }
  }, [item, resultText, onDone]);

  const submitValidate = useCallback(async () => {
    setBusy(true);
    try {
      let draft = draftText;
      if (!draft.trim()) {
        const draftRes = await callApi<{ draft_json: string }>("/api/generate-draft", {
          run_id: item.run_id,
          work_item_id: item.work_item_id,
        });
        draft = draftRes.draft_json;
        setDraftText(draft);
      }
      const data = await callApi<{ report: ValidationReport }>("/api/validate", {
        run_id: item.run_id,
        work_item_id: item.work_item_id,
        draft,
      });
      setValidation(data.report);
      if (data.report.status === "rejected") {
        toast.error("Draft doğrulaması reddedildi");
      } else {
        toast.success(`Doğrulama sonucu: ${data.report.status}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Validate komutu başarısız");
    } finally {
      setBusy(false);
    }
  }, [item, draftText]);

  const submitApprove = useCallback(async () => {
    if (!draftText.trim() || validation?.status !== "valid") {
      toast.error("Önce taslağı doğrulayın (Validate) — yalnız geçerli bir taslak kaydedilebilir");
      return;
    }
    setBusy(true);
    try {
      const data = await callApi<{ approved_path: string }>("/api/approve", {
        run_id: item.run_id,
        work_item_id: item.work_item_id,
        draft: draftText,
      });
      toast.success(`Olay onaylandı ve kaydedildi: ${data.approved_path}`);
      onDone();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Approve komutu başarısız");
    } finally {
      setBusy(false);
    }
  }, [item, draftText, validation, onDone]);

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Panoya kopyalandı");
  };

  const downloadArtifact = (text: string, filename: string) => {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <Card className="border-primary/30 bg-card/80 shadow-md">
      <CardHeader className="bg-muted/30 border-b border-border/60 pb-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary border border-primary/20 font-mono font-bold text-sm">
              {isScreeningRun ? <Sparkles className="h-4 w-4" /> : `$${item.ticker}`}
            </div>
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                {isScreeningRun ? (
                  <span>Fikir Taraması Sonucu</span>
                ) : (
                  <Link href={`/companies/${item.ticker}`} className="hover:underline">
                    {item.ticker}
                  </Link>
                )}
                <Badge variant="outline" className="font-mono text-xs">
                  {item.workflow}
                </Badge>
                {item.workflow !== item.requested_workflow && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1 font-mono">
                    <ArrowRight className="h-3 w-3" />
                    {item.requested_workflow}
                  </span>
                )}
                <SkillBadge workflow={item.workflow} />
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">{item.reason}</p>
            </div>
          </div>
          {!isScreeningRun && (
            <Link
              href={`/companies/${item.ticker}`}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              Şirket sayfası <ArrowUpRight className="h-3 w-3" />
            </Link>
          )}
        </div>
      </CardHeader>

      <CardContent className="p-6 space-y-6">
        {/* Step 1: Pack Preparation */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-muted text-[10px] font-bold">1</span>
              Veri Paketi
            </div>
            {artifactDir && (
              <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
                <CheckCircle2 className="h-3.5 w-3.5" /> Hazır
              </div>
            )}
          </div>

          {!artifactDir ? (
            <div className="flex items-center gap-3">
              <Button onClick={runPrepare} disabled={preparing} size="sm" className="gap-2">
                {preparing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
                Paketi Hazırla
              </Button>
              <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={refresh}
                  onChange={(e) => setRefresh(e.target.checked)}
                  className="rounded border-border text-primary focus:ring-primary h-3.5 w-3.5"
                />
                SEC verilerini tazele
              </label>
            </div>
          ) : (
            <div className="flex items-center gap-3 text-xs">
              <button
                onClick={() => setShowArtifacts((v) => !v)}
                className="flex items-center gap-1 text-muted-foreground hover:text-foreground"
              >
                {showArtifacts ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                Pack dosyalarını göster
              </button>
              {item.work_item_id && (
                <button onClick={runPrepare} className="text-muted-foreground hover:text-foreground underline decoration-dotted">
                  yeniden hazırla
                </button>
              )}
            </div>
          )}

          {artifactDir && showArtifacts && (
            <div className="mt-1 space-y-2 p-3 rounded-lg bg-muted/30 border border-border/60">
              <div className="text-[11px] font-mono text-muted-foreground truncate">
                Dizin: <span className="text-foreground">{artifactDir}</span>
              </div>
              <div className="flex gap-2 pt-1">
                <Button variant="outline" size="sm" onClick={() => viewArtifact(`${artifactDir}/instructions.md`)} className="h-7 text-xs gap-1.5">
                  <FileText className="h-3.5 w-3.5 text-sky-500" /> instructions.md
                </Button>
                <Button variant="outline" size="sm" onClick={() => viewArtifact(`${artifactDir}/pack.json`)} className="h-7 text-xs gap-1.5">
                  <FileCode className="h-3.5 w-3.5 text-emerald-500" /> pack.json
                </Button>
              </div>
              {artifactContent && (
                <div className="mt-2 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground font-mono px-1">
                    <span>Görüntülenen: {activeArtifactFile}</span>
                    <div className="flex items-center gap-3">
                      <button onClick={() => copyToClipboard(artifactContent)} className="flex items-center gap-1 hover:text-foreground">
                        <Copy className="h-3 w-3" /> Kopyala
                      </button>
                      <button onClick={() => downloadArtifact(artifactContent, activeArtifactFile ?? "artifact.txt")} className="flex items-center gap-1 hover:text-foreground">
                        <FileDown className="h-3 w-3" /> İndir
                      </button>
                    </div>
                  </div>
                  <ScrollArea className="h-64 rounded-md border border-border/80 bg-background/80 p-3">
                    <pre className="font-mono text-xs text-foreground/90 whitespace-pre-wrap">{artifactContent}</pre>
                  </ScrollArea>
                </div>
              )}
            </div>
          )}
        </div>

        <Separator className="bg-border/60" />

        {/* Step 2: Analysis — codex is the primary path */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-muted text-[10px] font-bold">2</span>
              Analiz
            </div>
            {resultText && (
              <div className="flex items-center gap-1.5 text-emerald-600 dark:text-emerald-400 text-xs font-medium">
                <CheckCircle2 className="h-3.5 w-3.5" /> Sonuç bağlandı
              </div>
            )}
          </div>

          <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-violet-600 dark:text-violet-400">
                <Terminal className="h-4 w-4" />
                Codex ile Otomatik Çalıştır
              </div>
              {skillBadge && (
                <span className="text-[11px] font-mono text-muted-foreground">
                  {skillBadge.model} · {skillBadge.effort} reasoning
                </span>
              )}
            </div>
            <p className="text-[11px] text-muted-foreground">
              Gerçek PEI eklentisi (idea-generation, initiating-coverage, ...)
              web aramasıyla çalışır, sonucu otomatik bağlar ve taslağı üretir.
            </p>
            <Button onClick={runCodexAuto} disabled={codexRunning || busy} className="gap-2 bg-violet-600 hover:bg-violet-700 text-white">
              {codexRunning ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Terminal className="h-3.5 w-3.5" />}
              {codexRunning ? "Çalışıyor — birkaç dakika sürebilir..." : "Codex ile Çalıştır"}
            </Button>
          </div>

          <button
            onClick={() => setShowManualPaste((v) => !v)}
            className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
          >
            {showManualPaste ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            Alternatif: ChatGPT/LLM çıktısını elle yapıştır
          </button>

          {showManualPaste && (
            <div className="space-y-2 pl-1">
              <Textarea
                placeholder="ChatGPT veya LLM'den aldığınız yanıt çıktısını buraya yapıştırın..."
                value={resultText}
                onChange={(e) => setResultText(e.target.value)}
                className="min-h-28 font-mono text-xs border-border/80 bg-background/50 focus:bg-background"
              />
              <Button size="sm" variant="outline" onClick={submitAttach} disabled={busy} className="gap-2">
                {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                Kaydet ve Bağla
              </Button>
            </div>
          )}
        </div>

        <Separator className="bg-border/60" />

        {/* Step 3: Draft, Validate, Approve */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-muted text-[10px] font-bold">3</span>
              Doğrula ve Onayla
            </div>
            <button
              onClick={() => setShowRawDraft((v) => !v)}
              className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
            >
              {showRawDraft ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              Ham JSON&apos;u {draftText ? "göster" : "elle oluştur"}
            </button>
          </div>

          {!draftText && !showRawDraft && (
            <p className="text-xs text-muted-foreground">
              Adım 2 tamamlanınca taslak otomatik üretilir. Elle tetiklemek isterseniz yukarıdaki bağlantıyı kullanın.
            </p>
          )}

          {showRawDraft && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <p className="text-[11px] text-amber-600 dark:text-amber-400">
                  agy (Gemini) ile şemaya zorlanmış çıkarım — onaylamadan önce alanları gözden geçirin.
                </p>
                <Button size="sm" variant="ghost" onClick={runGenerateDraft} disabled={busy} className="h-6 text-[11px] gap-1 text-sky-500">
                  <Sparkles className="h-3 w-3" /> Yeniden çıkar
                </Button>
              </div>
              <Textarea
                placeholder='{"schema_version": 1, "event_type": "...", ...}'
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                className="min-h-36 font-mono text-xs border-border/80 bg-background/50 focus:bg-background"
              />
            </div>
          )}

          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={submitValidate} disabled={busy} className="gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              Doğrula
            </Button>
            <Button
              size="sm"
              onClick={submitApprove}
              disabled={busy || validation?.status !== "valid"}
              className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Onayla ve Kaydet
            </Button>
          </div>

          {validation && (
            <div
              className={cn(
                "mt-1 flex items-center justify-between p-3 rounded-lg border text-xs",
                validation.status === "valid"
                  ? "border-emerald-500/30 bg-emerald-500/5"
                  : validation.status === "rejected"
                  ? "border-rose-500/30 bg-rose-500/5"
                  : "border-amber-500/30 bg-amber-500/5"
              )}
            >
              <span className="font-semibold">Doğrulama sonucu</span>
              <Badge
                variant={
                  validation.status === "valid" ? "default" : validation.status === "rejected" ? "destructive" : "secondary"
                }
                className="font-mono"
              >
                {validation.status}
              </Badge>
            </div>
          )}
          {validation && validation.status !== "valid" && (
            <ScrollArea className="h-40 rounded-md border border-border/80 bg-background/80 p-3">
              <pre className="font-mono text-xs text-foreground/90 whitespace-pre-wrap">{JSON.stringify(validation, null, 2)}</pre>
            </ScrollArea>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

type BatchStage = "queued" | "preparing" | "running" | "drafting" | "done" | "error";

const BATCH_STAGE_LABEL: Record<BatchStage, string> = {
  queued: "Sırada",
  preparing: "Pack hazırlanıyor",
  running: "Codex çalışıyor",
  drafting: "Taslak çıkarılıyor",
  done: "Tamamlandı",
  error: "Hata",
};

export function WorkQueue({
  items,
  onChanged,
}: {
  items: NextItem[];
  onChanged: () => void;
}) {
  const [selected, setSelected] = useState<NextItem | null>(items.length > 0 ? items[0] : null);
  const [batchSelected, setBatchSelected] = useState<Set<string>>(new Set());
  const [batchRunning, setBatchRunning] = useState(false);
  const [batchProgress, setBatchProgress] = useState<Map<string, BatchStage>>(new Map());

  const eligible = useMemo(() => items.filter((i) => i.work_item_id), [items]);

  const toggleBatch = (id: string) => {
    setBatchSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const toggleBatchAll = () => {
    setBatchSelected((prev) =>
      prev.size === eligible.length ? new Set() : new Set(eligible.map((i) => i.work_item_id as string)),
    );
  };

  const runBatchPrepare = async () => {
    const targets = eligible.filter((i) => batchSelected.has(i.work_item_id as string) && i.action === "prepare");
    if (!targets.length) return;
    setBatchRunning(true);
    const results = await Promise.allSettled(
      targets.map((i) => callApi("/api/prepare", { work_item_id: i.work_item_id, no_refresh: true })),
    );
    const failed = results.filter((r) => r.status === "rejected").length;
    if (failed) toast.error(`${targets.length - failed}/${targets.length} hazırlandı, ${failed} başarısız`);
    else toast.success(`${targets.length} paket hazırlandı`);
    setBatchRunning(false);
    onChanged();
  };

  // Codex + draft ucret cikaran islemi paralel degil, SIRALI calistirir --
  // her adimin sonunda attach_result events.jsonl'a yazar (append_events
  // oku-degistir-yaz yapiyor, es zamanli iki yazma birbirini ezebilir).
  // Onaylamak (approve) hala kullanicinin elle yapacagi, ayri bir adim.
  const runBatchCodex = async () => {
    const targets = eligible.filter((i) => batchSelected.has(i.work_item_id as string));
    if (!targets.length) return;
    setBatchRunning(true);
    const progress = new Map<string, BatchStage>(targets.map((i) => [i.work_item_id as string, "queued"]));
    setBatchProgress(new Map(progress));

    for (const item of targets) {
      const id = item.work_item_id as string;
      try {
        if (item.action === "prepare") {
          progress.set(id, "preparing");
          setBatchProgress(new Map(progress));
          await callApi("/api/prepare", { work_item_id: id, no_refresh: true });
        }
        progress.set(id, "running");
        setBatchProgress(new Map(progress));
        const codexRes = await callApi<{ result_path: string }>("/api/run-codex", {
          run_id: item.run_id,
          work_item_id: id,
        });
        progress.set(id, "drafting");
        setBatchProgress(new Map(progress));
        await callApi("/api/generate-draft", { run_id: item.run_id, work_item_id: id });
        void codexRes;
        progress.set(id, "done");
        setBatchProgress(new Map(progress));
      } catch (err) {
        progress.set(id, "error");
        setBatchProgress(new Map(progress));
        toast.error(`${item.ticker}: ${err instanceof Error ? err.message : "başarısız oldu"}`);
      }
      onChanged();
    }

    const doneCount = Array.from(progress.values()).filter((s) => s === "done").length;
    toast.success(`Toplu çalıştırma bitti: ${doneCount}/${targets.length} hazır, gözden geçirip onaylayın`);
    setBatchRunning(false);
    setBatchSelected(new Set());
  };

  return (
    <div className="space-y-6">
      {eligible.length > 0 && (
        <div className="flex flex-wrap items-center gap-3 p-3 rounded-lg border border-border/80 bg-card/60">
          <span className="text-xs text-muted-foreground font-medium">
            {batchSelected.size} seçili
          </span>
          <Button
            size="sm"
            variant="outline"
            onClick={runBatchPrepare}
            disabled={batchRunning || batchSelected.size === 0}
            className="gap-1.5"
          >
            <Play className="h-3.5 w-3.5" />
            Yalnız Hazırla
          </Button>
          <Button
            size="sm"
            onClick={runBatchCodex}
            disabled={batchRunning || batchSelected.size === 0}
            className="gap-1.5 bg-violet-600 hover:bg-violet-700 text-white"
          >
            {batchRunning ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Terminal className="h-3.5 w-3.5" />}
            Codex ile Çalıştır (uçtan uca)
          </Button>
          <span className="text-[11px] text-muted-foreground">
            Seçilenler sırayla hazırlanır → codex çalışır → taslak çıkarılır. Onay hâlâ elle.
          </span>
        </div>
      )}

      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-8">
                {eligible.length > 0 && (
                  <input
                    type="checkbox"
                    checked={batchSelected.size === eligible.length && eligible.length > 0}
                    onChange={toggleBatchAll}
                  />
                )}
              </TableHead>
              <TableHead className="w-24 font-bold">Ticker</TableHead>
              <TableHead className="w-32">Workflow</TableHead>
              <TableHead className="w-28">Model</TableHead>
              <TableHead className="w-32">Durum</TableHead>
              <TableHead>Neden / Açıklama</TableHead>
              <TableHead className="w-28 text-right">İşlem</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const id = item.work_item_id;
              const isSelected =
                selected?.work_item_id === item.work_item_id ||
                (selected?.run_id === item.run_id && selected?.ticker === item.ticker);
              const stage = id ? batchProgress.get(id) : undefined;

              return (
                <TableRow
                  key={id ?? `${item.run_id}-${item.ticker}`}
                  className={isSelected ? "bg-primary/10 font-medium" : "hover:bg-muted/20"}
                >
                  <TableCell>
                    {id && (
                      <input
                        type="checkbox"
                        checked={batchSelected.has(id)}
                        onChange={() => toggleBatch(id)}
                        disabled={batchRunning}
                      />
                    )}
                  </TableCell>
                  <TableCell className="font-bold font-mono text-sm">
                    <Link href={`/companies/${item.ticker}`} className="hover:underline">
                      <span className="text-primary mr-0.5">$</span>
                      {item.ticker}
                    </Link>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {item.workflow}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <SkillBadge workflow={item.workflow} />
                  </TableCell>
                  <TableCell>
                    {stage ? (
                      <Badge
                        variant={stage === "done" ? "default" : stage === "error" ? "destructive" : "secondary"}
                        className="text-[11px] gap-1"
                      >
                        {stage === "done" && <CheckCircle2 className="h-3 w-3" />}
                        {stage === "error" && <XCircle className="h-3 w-3" />}
                        {(stage === "preparing" || stage === "running" || stage === "drafting") && (
                          <RefreshCw className="h-3 w-3 animate-spin" />
                        )}
                        {BATCH_STAGE_LABEL[stage]}
                      </Badge>
                    ) : (
                      <Badge variant={item.action === "prepare" ? "default" : "secondary"} className="text-[11px]">
                        {item.action === "prepare" ? "Prepare Bekliyor" : "Sonuç Bekliyor"}
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-md truncate">{item.reason}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant={isSelected ? "default" : "outline"}
                      onClick={() => setSelected(item)}
                      className="h-7 text-xs"
                    >
                      {isSelected ? "Açık" : "İncele"}
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}

            {items.length === 0 && (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground">
                  <div className="flex flex-col items-center justify-center gap-1">
                    <CheckCircle2 className="h-6 w-6 text-emerald-500" />
                    <span>Kuyrukta bekleyen iş bulunmuyor.</span>
                  </div>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      {selected && <WorkItemDetail item={selected} onDone={onChanged} />}
    </div>
  );
}
