import { NextResponse } from "next/server";
import { runBridge, BridgeError } from "@/lib/bridge";
import type { WatchlistPayload } from "@/lib/types";

export async function GET() {
  try {
    const payload = await runBridge<WatchlistPayload>("watchlist-get");
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const payload = await runBridge<WatchlistPayload>("watchlist-update", body);
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

export async function DELETE(req: Request) {
  try {
    const body = await req.json();
    const payload = await runBridge<WatchlistPayload>("watchlist-delete", body);
    return NextResponse.json(payload);
  } catch (err) {
    const message = err instanceof BridgeError ? err.message : "unexpected error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
