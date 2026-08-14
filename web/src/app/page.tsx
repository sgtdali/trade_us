"use client";

import { Overview } from "@/components/panel/overview";
import { useAppData } from "@/lib/app-data";

export default function Home() {
  const { status, refresh } = useAppData();
  return <Overview status={status} onChanged={refresh} />;
}
