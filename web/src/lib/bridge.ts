import { spawn } from "child_process";
import path from "path";

const REPO_ROOT = path.resolve(process.cwd(), "..");
const BRIDGE_SCRIPT = path.join(REPO_ROOT, "scripts", "us_pei_dashboard_bridge.py");

export class BridgeError extends Error {}

// Es zamanli birden fazla python.exe spawn'i Windows'ta ara sira
// STATUS_DLL_INIT_FAILED (0xC0000142) ile cakisiyor. Cagrilari tek dosyalik
// bir kuyrukta sirala; panel zaten interaktif tek kullanicili oldugu icin
// bunun gozle gorulur bir gecikme maliyeti yok.
let queue: Promise<unknown> = Promise.resolve();

function spawnBridge<T>(command: string, args: Record<string, unknown>): Promise<T> {
  return new Promise((resolve, reject) => {
    // shell: true -- Windows'ta Node'un dogrudan CreateProcess ile python.exe
    // baslatmasi bazi kurulumlarda DLL init hatasi (0xC0000142) veriyor;
    // cmd.exe uzerinden calistirmak ortami dogru kurup bu hatayi engelliyor.
    const child = spawn("python", [BRIDGE_SCRIPT, command], {
      cwd: REPO_ROOT,
      shell: true,
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => (stdout += chunk));
    child.stderr.on("data", (chunk) => (stderr += chunk));

    child.on("error", (err) => reject(new BridgeError(err.message)));

    child.on("close", (code) => {
      if (!stdout.trim()) {
        reject(new BridgeError(stderr.trim() || `bridge exited with code ${code} and no output`));
        return;
      }
      let parsed: unknown;
      try {
        parsed = JSON.parse(stdout);
      } catch {
        reject(new BridgeError(stderr || stdout || "bridge returned invalid JSON"));
        return;
      }
      const record = parsed as { error?: string };
      if (record && typeof record === "object" && record.error) {
        reject(new BridgeError(record.error));
        return;
      }
      if (code !== 0) {
        reject(new BridgeError(stderr.trim() || `bridge exited with code ${code}`));
        return;
      }
      resolve(parsed as T);
    });

    child.stdin.write(JSON.stringify(args));
    child.stdin.end();
  });
}

export function runBridge<T = unknown>(
  command: string,
  args: Record<string, unknown> = {},
): Promise<T> {
  const run = queue.then(() => spawnBridge<T>(command, args));
  // Bir cagri reddedilse bile kuyruk zincirini kirmasin diye hatayi yutan
  // ayri bir kol tutuyoruz; asil sonuc/hata caginin sahibine `run` uzerinden
  // ulasir.
  queue = run.catch(() => undefined);
  return run;
}
