"use client";

import { useCallback, useState } from "react";
import { toast } from "sonner";
import {
  AlertCircle,
  ArrowRight,
  CheckCircle2,
  Copy,
  FileCode,
  FileDown,
  FileText,
  ListTodo,
  Play,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  Terminal,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { callApi } from "@/lib/api";
import type { NextItem, ValidationReport } from "@/lib/types";

export function WorkItemDetail({ item, onDone }: { item: NextItem; onDone: () => void }) {
  const [refresh, setRefresh] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const [artifactDir, setArtifactDir] = useState<string | null>(item.artifact_dir ?? null);
  const [artifactContent, setArtifactContent] = useState<string | null>(null);
  const [activeArtifactFile, setActiveArtifactFile] = useState<string | null>(null);
  const [resultText, setResultText] = useState("");
  const [draftText, setDraftText] = useState("");
  const [validation, setValidation] = useState<ValidationReport | null>(null);
  const [busy, setBusy] = useState(false);

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
      
      // Auto-generate draft JSON right after attaching result
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
      const data = await callApi<{ report: ValidationReport }>("/api/validate", {
        run_id: item.run_id,
        work_item_id: item.work_item_id,
        draft: draftText,
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
  }, [item, draftText, onDone]);

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
              ${item.ticker}
            </div>
            <div>
              <CardTitle className="flex items-center gap-2 text-base">
                <span>{item.ticker}</span>
                <Badge variant="outline" className="font-mono text-xs">
                  {item.workflow}
                </Badge>
                {item.workflow !== item.requested_workflow && (
                  <span className="text-xs text-muted-foreground flex items-center gap-1 font-mono">
                    <ArrowRight className="h-3 w-3" />
                    {item.requested_workflow}
                  </span>
                )}
              </CardTitle>
              <CardDescription className="text-xs mt-0.5">{item.reason}</CardDescription>
            </div>
          </div>

          <Badge
            variant={item.action === "prepare" ? "default" : "secondary"}
            className="font-medium text-xs px-2.5 py-1"
          >
            {item.action === "prepare" ? "1. Adım: Prepare Gerekiyor" : "2. Adım: Sonuç Yapıştır"}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="p-6 space-y-6">
        {/* Step 1: Pack Preparation */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Terminal className="h-4 w-4 text-primary" />
              Adım 1: Veri Paketi Hazırlığı (pack.json)
            </div>
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

          <div className="flex items-center gap-3">
            <Button onClick={runPrepare} disabled={preparing} size="sm" className="gap-2">
              {preparing ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Play className="h-3.5 w-3.5" />}
              Paketi Hazırla (Prepare)
            </Button>
          </div>

          {artifactDir && (
            <div className="mt-3 space-y-2 p-3 rounded-lg bg-muted/30 border border-border/60">
              <div className="text-[11px] font-mono text-muted-foreground truncate">
                Dizin: <span className="text-foreground">{artifactDir}</span>
              </div>
              <div className="flex gap-2 pt-1">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => viewArtifact(`${artifactDir}/instructions.md`)}
                  className="h-7 text-xs gap-1.5"
                >
                  <FileText className="h-3.5 w-3.5 text-sky-500" />
                  instructions.md
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => viewArtifact(`${artifactDir}/pack.json`)}
                  className="h-7 text-xs gap-1.5"
                >
                  <FileCode className="h-3.5 w-3.5 text-emerald-500" />
                  pack.json
                </Button>
              </div>

              {artifactContent && (
                <div className="mt-2 space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground font-mono px-1">
                    <span>Görüntülenen: {activeArtifactFile}</span>
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => copyToClipboard(artifactContent)}
                        className="flex items-center gap-1 hover:text-foreground"
                      >
                        <Copy className="h-3 w-3" /> Kopyala
                      </button>
                      <button
                        onClick={() =>
                          downloadArtifact(artifactContent, activeArtifactFile ?? "artifact.txt")
                        }
                        className="flex items-center gap-1 hover:text-foreground"
                      >
                        <FileDown className="h-3 w-3" /> İndir
                      </button>
                    </div>
                  </div>
                  <ScrollArea className="h-64 rounded-md border border-border/80 bg-background/80 p-3">
                    <pre className="font-mono text-xs text-foreground/90 whitespace-pre-wrap">
                      {artifactContent}
                    </pre>
                  </ScrollArea>
                </div>
              )}
            </div>
          )}
        </div>

        <Separator className="bg-border/60" />

        {/* Step 2: LLM / ChatGPT Analysis Result */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <Sparkles className="h-4 w-4 text-sky-500" />
              Adım 2: ChatGPT / LLM Analiz Sonucunu Bağla
            </div>
            {resultText && (
              <span className="text-[11px] font-mono text-muted-foreground">
                {resultText.length} karakter
              </span>
            )}
          </div>

          <Textarea
            placeholder="ChatGPT veya LLM'den aldığınız yanıt çıktısını buraya yapıştırın..."
            value={resultText}
            onChange={(e) => setResultText(e.target.value)}
            className="min-h-32 font-mono text-xs border-border/80 bg-background/50 focus:bg-background"
          />

          <Button size="sm" onClick={submitAttach} disabled={busy} className="gap-2">
            {busy ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
            Kaydet ve Bağla (Attach Result)
          </Button>
        </div>

        <Separator className="bg-border/60" />

        {/* Step 3: Draft Validation & Approval */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="text-xs font-semibold text-foreground uppercase tracking-wider flex items-center gap-1.5">
              <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              Adım 3: Draft Olay Doğrulama ve Onay (draft.json)
            </div>
            <Button
              size="sm"
              variant="outline"
              onClick={runGenerateDraft}
              disabled={busy}
              className="h-7 text-xs gap-1.5 border-sky-500/40 text-sky-500 hover:bg-sky-500/10 font-medium"
            >
              {busy ? (
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              Taslağı agy (Gemini) ile Çıkar
            </Button>
          </div>

          <p className="text-xs text-amber-600 dark:text-amber-400">
            Bu taslak agy CLI üzerinden şemaya zorlanmış bir LLM çağrısıyla
            çıkarıldı (regex/tablo ayrıştırma değil) — yine de onaylamadan
            önce alanları gözden geçirin.
          </p>

          <Textarea
            placeholder='{"schema_version": 1, "event_type": "...", ...}'
            value={draftText}
            onChange={(e) => setDraftText(e.target.value)}
            className="min-h-36 font-mono text-xs border-border/80 bg-background/50 focus:bg-background"
          />

          <div className="flex items-center gap-2">
            <Button size="sm" variant="secondary" onClick={submitValidate} disabled={busy} className="gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-amber-500" />
              Doğrula (Validate)
            </Button>
            <Button size="sm" onClick={submitApprove} disabled={busy} className="gap-1.5 bg-emerald-600 hover:bg-emerald-700 text-white">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Onayla ve Kaydet (Approve)
            </Button>
          </div>

          {validation && (
            <div className="mt-3 space-y-2 p-3 rounded-lg border border-border/60 bg-muted/30">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">Doğrulama Raporu:</span>
                <Badge
                  variant={
                    validation.status === "valid"
                      ? "default"
                      : validation.status === "rejected"
                      ? "destructive"
                      : "secondary"
                  }
                  className="font-mono text-xs"
                >
                  {validation.status}
                </Badge>
              </div>
              <ScrollArea className="h-48 rounded-md border border-border/80 bg-background/80 p-3">
                <pre className="font-mono text-xs text-foreground/90 whitespace-pre-wrap">
                  {JSON.stringify(validation, null, 2)}
                </pre>
              </ScrollArea>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function WorkQueue({
  items,
  onChanged,
}: {
  items: NextItem[];
  onChanged: () => void;
}) {
  const [selected, setSelected] = useState<NextItem | null>(items.length > 0 ? items[0] : null);

  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-28 font-bold">Ticker</TableHead>
              <TableHead className="w-36">Workflow</TableHead>
              <TableHead className="w-36">Durum / Aksiyon</TableHead>
              <TableHead>Neden / Açıklama</TableHead>
              <TableHead className="w-32 text-right">İşlem</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {items.map((item) => {
              const isSelected = selected?.work_item_id === item.work_item_id || (selected?.run_id === item.run_id && selected?.ticker === item.ticker);
              return (
                <TableRow
                  key={item.work_item_id ?? `${item.run_id}-${item.ticker}`}
                  className={isSelected ? "bg-primary/10 font-medium" : "hover:bg-muted/20"}
                >
                  <TableCell className="font-bold font-mono text-sm">
                    <span className="text-primary mr-0.5">$</span>
                    {item.ticker}
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline" className="font-mono text-xs">
                      {item.workflow}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={item.action === "prepare" ? "default" : "secondary"}
                      className="text-[11px]"
                    >
                      {item.action === "prepare" ? "Prepare Bekliyor" : "Sonuç Bekliyor"}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground max-w-md truncate">
                    {item.reason}
                  </TableCell>
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
                <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
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

      {selected && (
        <WorkItemDetail
          item={selected}
          onDone={() => {
            onChanged();
          }}
        />
      )}
    </div>
  );
}
