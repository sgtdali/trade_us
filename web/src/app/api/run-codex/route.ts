import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";

export async function POST(request: Request) {
  const body = await request.json();
  try {
    const result = await runBridge<{ result_path: string }>("run-codex", {
      run_id: body.run_id,
      work_item_id: body.work_item_id || null,
    });
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
