import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";

export async function POST(request: Request) {
  const body = await request.json().catch(() => ({}));
  try {
    const result = await runBridge<{ additions: unknown[]; data_path: string | null }>(
      "check-triggers",
      { refresh: body.refresh ?? false },
    );
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
