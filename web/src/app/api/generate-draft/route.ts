import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const payload = await runBridge<{ draft_json: string; draft: unknown }>("generate-draft", body);
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
