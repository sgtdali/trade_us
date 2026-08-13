import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";
import type { CatalogPayload } from "@/lib/types";

export async function GET() {
  try {
    const payload = await runBridge<CatalogPayload>("catalog");
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
