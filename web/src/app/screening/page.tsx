"use client";

import { IdeaRuns } from "@/components/panel/idea-runs";
import { useAppData } from "@/lib/app-data";

export default function ScreeningPage() {
  const { status, refresh } = useAppData();
  return <IdeaRuns runs={status?.runs ?? []} onChanged={refresh} />;
}
