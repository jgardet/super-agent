// ─────────────────────────────────────────────────────────────────────────────
// OpenCode HTTP shim
// Exposes a tiny REST API over `opencode run` so the orchestrator can delegate
// real file operations (read/write/edit/run) into the shared /workspace volume.
//
// Endpoints:
//   GET  /health                   → { ok: true, cwd, model }
//   POST /run   { prompt, cwd?, timeout_ms?, model? }
//                                  → { stdout, stderr, exit_code, duration_ms }
//
// The shim intentionally does NOT stream; the orchestrator's coding crew
// makes synchronous calls inside CrewAI tool execution.
// ─────────────────────────────────────────────────────────────────────────────

import http from "node:http";
import { spawn } from "node:child_process";

const PORT        = parseInt(process.env.SHIM_PORT || "8787", 10);
const HOST        = process.env.SHIM_HOST || "0.0.0.0";
const DEFAULT_CWD = process.env.SHIM_DEFAULT_CWD || "/workspace";
const DEFAULT_MODEL = process.env.OPENCODE_MODEL || "minimax-m2.7:cloud";
const DEFAULT_TIMEOUT_MS = parseInt(process.env.SHIM_TIMEOUT_MS || "180000", 10);

function readJson(req) {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (c) => { data += c; if (data.length > 1_000_000) reject(new Error("payload too large")); });
    req.on("end", () => { try { resolve(data ? JSON.parse(data) : {}); } catch (e) { reject(e); } });
    req.on("error", reject);
  });
}

function send(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    "content-type": "application/json",
    "content-length": Buffer.byteLength(body),
  });
  res.end(body);
}

function runOpencode({ prompt, cwd, timeout_ms, model }) {
  return new Promise((resolve) => {
    const started = Date.now();
    const args = ["run", "--print-logs"];
    if (model) args.push("--model", model);
    args.push(prompt);

    const child = spawn("opencode", args, {
      cwd: cwd || DEFAULT_CWD,
      env: { ...process.env, OPENCODE_MODEL: model || DEFAULT_MODEL },
    });

    let stdout = "";
    let stderr = "";
    let timedOut = false;

    const killer = setTimeout(() => {
      timedOut = true;
      try { child.kill("SIGKILL"); } catch {}
    }, timeout_ms || DEFAULT_TIMEOUT_MS);

    child.stdout.on("data", (c) => { stdout += c.toString(); });
    child.stderr.on("data", (c) => { stderr += c.toString(); });
    child.on("close", (code) => {
      clearTimeout(killer);
      resolve({
        stdout,
        stderr,
        exit_code: code ?? -1,
        timed_out: timedOut,
        duration_ms: Date.now() - started,
      });
    });
    child.on("error", (err) => {
      clearTimeout(killer);
      resolve({
        stdout,
        stderr: stderr + `\nshim: spawn error: ${err.message}`,
        exit_code: -1,
        timed_out: false,
        duration_ms: Date.now() - started,
      });
    });
  });
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/health") {
      return send(res, 200, { ok: true, cwd: DEFAULT_CWD, model: DEFAULT_MODEL });
    }
    if (req.method === "POST" && req.url === "/run") {
      const body = await readJson(req);
      if (!body.prompt || typeof body.prompt !== "string") {
        return send(res, 400, { error: "missing or invalid 'prompt'" });
      }
      const result = await runOpencode({
        prompt: body.prompt,
        cwd: body.cwd,
        timeout_ms: body.timeout_ms,
        model: body.model,
      });
      return send(res, 200, result);
    }
    send(res, 404, { error: "not found", hint: "GET /health, POST /run" });
  } catch (e) {
    send(res, 500, { error: String(e && e.message || e) });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`[opencode-shim] listening on http://${HOST}:${PORT} (cwd=${DEFAULT_CWD}, model=${DEFAULT_MODEL})`);
});
