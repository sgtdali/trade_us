"use client";

import { ArrowRight, BookOpen, CheckCircle2, Layers } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { CatalogPayload } from "@/lib/types";

export function Catalog({ catalog }: { catalog: CatalogPayload | null }) {
  const entries = Object.entries(catalog?.workflows ?? {});

  return (
    <div className="space-y-6">
      {/* Header Info Card */}
      <Card className="border-border/80 bg-card/60">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            PEI Workflow Katalog & Kontrat Tanımları
          </CardTitle>
          <CardDescription className="text-xs">
            Sistemde tanımlı tüm workflow adımları, ön koşullar ve izin verilen geçiş rotaları.
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Main Catalog Table */}
      <div className="rounded-lg border border-border/80 overflow-hidden bg-card/60 shadow-xs">
        <Table>
          <TableHeader className="bg-muted/40">
            <TableRow>
              <TableHead className="w-40 font-bold">Workflow Adı</TableHead>
              <TableHead className="w-32">Pack Adımı</TableHead>
              <TableHead className="w-48">Ön Koşul Workflow&apos;lar</TableHead>
              <TableHead className="w-56">İzin Verilen Sonraki Adımlar</TableHead>
              <TableHead>Sonuç Sözleşmesi (Result Contract)</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {entries.map(([name, w]) => (
              <TableRow key={name} className="hover:bg-muted/20 border-b border-border/40">
                <TableCell className="font-bold font-mono text-sm">
                  <Badge variant="default" className="font-mono text-xs">
                    {name}
                  </Badge>
                </TableCell>
                <TableCell className="font-mono text-xs font-medium text-foreground/90">
                  {w.pack_step ? (
                    <Badge variant="outline" className="font-mono text-[10px]">
                      {w.pack_step}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {w.required_workflows.length > 0 ? (
                      w.required_workflows.map((r) => (
                        <Badge key={r} variant="outline" className="font-mono text-[10px] bg-background">
                          {r}
                        </Badge>
                      ))
                    ) : (
                      <span className="text-muted-foreground text-xs font-mono">Yok (İlk Adım)</span>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1.5 items-center">
                    {w.allowed_next.length > 0 ? (
                      w.allowed_next.map((r) => (
                        <span key={r} className="inline-flex items-center gap-1 text-[11px] font-mono">
                          <Badge variant="secondary" className="font-mono text-[10px]">
                            {r}
                          </Badge>
                        </span>
                      ))
                    ) : (
                      <span className="text-muted-foreground text-xs font-mono">Son Adım (Terminal)</span>
                    )}
                  </div>
                </TableCell>
                <TableCell className="font-mono text-xs text-muted-foreground">
                  <div className="p-2 rounded bg-muted/30 border border-border/40 text-[11px]">
                    {w.result_contract}
                  </div>
                </TableCell>
              </TableRow>
            ))}

            {entries.length === 0 && (
              <TableRow>
                <TableCell colSpan={5} className="h-32 text-center text-muted-foreground">
                  Katalog bilgisi bulunamadı.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
