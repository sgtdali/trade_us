import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";
import type { PortfolioPayload } from "@/lib/types";

export async function GET() {
  try {
    const payload = await runBridge<PortfolioPayload>("portfolio-get");
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const payload = await runBridge<PortfolioPayload>("portfolio-update", body);
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const body = await req.json();
    const payload = await runBridge<PortfolioPayload>("portfolio-delete", body);
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
