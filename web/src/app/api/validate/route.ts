import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";
import type { ValidationReport } from "@/lib/types";

export async function POST(request: Request) {
  const body = await request.json();
  try {
    const result = await runBridge<{ report: ValidationReport }>("validate", {
      run_id: body.run_id,
      work_item_id: body.work_item_id || null,
      draft: body.draft,
    });
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
