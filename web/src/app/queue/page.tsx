"use client";

import { WorkQueue } from "@/components/panel/work-queue";
import { useAppData } from "@/lib/app-data";

export default function QueuePage() {
  const { status, refresh } = useAppData();
  return <WorkQueue items={status?.next ?? []} onChanged={refresh} />;
}
