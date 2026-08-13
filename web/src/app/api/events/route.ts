import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";
import type { EventsPayload } from "@/lib/types";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const limit = searchParams.get("limit");
  try {
    const payload = await runBridge<EventsPayload>("events", {
      limit: limit ? Number(limit) : undefined,
    });
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
