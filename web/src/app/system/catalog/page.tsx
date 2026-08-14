"use client";

import { Catalog } from "@/components/panel/catalog";
import { useAppData } from "@/lib/app-data";

export default function CatalogPage() {
  const { catalog } = useAppData();
  return <Catalog catalog={catalog} />;
}
