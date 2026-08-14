"use client";

import { ThesisTracker } from "@/components/panel/thesis";
import { useAppData } from "@/lib/app-data";

export default function ThesisPage() {
  const { thesis, searchQuery } = useAppData();
  return <ThesisTracker theses={thesis?.theses ?? []} searchQuery={searchQuery} />;
}
