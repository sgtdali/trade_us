"use client";

import { CompaniesList } from "@/components/panel/companies-list";
import { useAppData } from "@/lib/app-data";

export default function CompaniesPage() {
  const { status, searchQuery } = useAppData();
  return <CompaniesList status={status} searchQuery={searchQuery} />;
}
