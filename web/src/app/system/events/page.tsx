"use client";

import { EventLog } from "@/components/panel/events";
import { useAppData } from "@/lib/app-data";

export default function EventsPage() {
  const { events, searchQuery } = useAppData();
  return <EventLog events={events?.events ?? []} searchQuery={searchQuery} />;
}
