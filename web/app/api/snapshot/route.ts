import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { NextResponse } from "next/server";

export async function GET() {
  try {
    const snapshotPath = join(process.cwd(), "public", "data", "a-stock-data.json");
    const snapshot = JSON.parse(await readFile(snapshotPath, "utf8"));
    return NextResponse.json(snapshot, {
      headers: {
        "Cache-Control": "no-store, no-cache, must-revalidate",
      },
    });
  } catch (reason) {
    return NextResponse.json(
      { error: "实时快照读取失败：" + String(reason) },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}
