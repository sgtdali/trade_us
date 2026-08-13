import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";
import type { StatusPayload } from "@/lib/types";

export async function GET() {
  try {
    const payload = await runBridge<StatusPayload>("status");
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
