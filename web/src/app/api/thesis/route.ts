import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";
import type { ThesisPayload } from "@/lib/types";

export async function GET() {
  try {
    const payload = await runBridge<ThesisPayload>("thesis");
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
