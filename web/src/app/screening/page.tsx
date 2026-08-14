"use client";

import { IdeaRuns } from "@/components/panel/idea-runs";
import { useAppData } from "@/lib/app-data";

export default function ScreeningPage() {
  const { refresh } = useAppData();
  return <IdeaRuns onChanged={refresh} />;
}
