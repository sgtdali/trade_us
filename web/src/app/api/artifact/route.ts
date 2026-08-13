import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const path = searchParams.get("path");
  if (!path) {
    return NextResponse.json({ error: "path is required" }, { status: 400 });
  }
  try {
    const result = await runBridge<{ content: string }>("artifact", { path });
    return NextResponse.json(result);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 400 });
  }
}
