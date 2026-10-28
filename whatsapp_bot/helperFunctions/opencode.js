/**
 * opencode bridge — the bot's brain for free-form requests.
 *
 * The bot never guesses what "sort these files by size" means. It asks the
 * local opencode agent to turn the request into something runnable, and to
 * work out a fix when a command fails.
 *
 * Transport is the `opencode` CLI (`opencode run --format json`) because it
 * handles service discovery and auth on its own — the HTTP API wants the
 * service password and rejects the free-tier models the server is configured
 * with for any client that isn't OpenCode itself.
 *
 * The `planner` agent is used by default: it has no shell, so it can read the
 * filesystem to plan a command but never runs anything itself — the bot is the
 * one that executes commands. Define it in ~/.config/opencode/opencode.json:
 *
 *   { "agent": { "planner": { "mode": "primary",
 *       "tools": { "bash": false, "write": false, "edit": false } } } }
 *
 * Env:
 *   OPENCODE_BIN         opencode binary (default: opencode)
 *   OPENCODE_AGENT       agent to use (default: planner)
 *   OPENCODE_MODEL       optional model override (default: server default)
 *   OPENCODE_TIMEOUT_MS  per-call timeout (default: 120000)
 */
const { spawn } = require("child_process");
const fs = require("fs");
require("dotenv").config();

const BIN = process.env.OPENCODE_BIN || "opencode";
const AGENT = process.env.OPENCODE_AGENT || "planner";
const MODEL = process.env.OPENCODE_MODEL || "";
const TIMEOUT_MS =
  Number(process.env.OPENCODE_TIMEOUT_MS) > 0
    ? Number(process.env.OPENCODE_TIMEOUT_MS)
    : 120000;

/**
 * Ask opencode one question.
 * Resolves {ok, text, error, sessionID} — never rejects.
 *
 * Uses spawn + the child's 'exit' event rather than execFile: opencode
 * leaves a helper process holding the stdout pipe, so execFile's callback
 * (which waits for the stream to reach EOF) never fires and the call hangs
 * until the timeout. 'exit' fires on the direct child and is what we want.
 */
function ask(prompt, opts = {}) {
  return new Promise((resolve) => {
    const args = ["run", "--format", "json"];
    if (AGENT) args.push("--agent", AGENT);
    if (MODEL) args.push("--model", MODEL);
    if (opts.sessionID) args.push("--session", opts.sessionID);
    args.push(String(prompt || ""));

    let cwd;
    if (opts.cwd && fs.existsSync(opts.cwd)) cwd = opts.cwd;

    const timeoutMs = opts.timeoutMs || TIMEOUT_MS;
    let child;
    try {
      child = spawn(BIN, args, {
        cwd,
        stdio: ["ignore", "pipe", "pipe"],
        env: { ...process.env, NO_COLOR: "1" },
      });
    } catch (e) {
      resolve({ ok: false, text: "", error: e.message, sessionID: "" });
      return;
    }

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      try {
        child.kill("SIGKILL");
      } catch (_) {}
      resolve({
        ok: false,
        text: "",
        error: `opencode timed out after ${Math.round(timeoutMs / 1000)}s`,
        sessionID: "",
      });
    }, timeoutMs);

    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };

    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("error", (e) => {
      finish({
        ok: false,
        text: "",
        error:
          e.code === "ENOENT"
            ? `${BIN} isn't installed (or isn't on PATH)`
            : e.message,
        sessionID: "",
      });
    });

    child.on("exit", (code, signal) => {
      // give the pipe a beat to flush the last chunk
      setTimeout(() => {
        const events = [];
        for (const line of stdout.split("\n")) {
          const t = line.trim();
          if (!t.startsWith("{")) continue;
          try {
            events.push(JSON.parse(t));
          } catch (_) {
            /* not every line is JSON — skip it */
          }
        }

        let text = "";
        let sessionID = opts.sessionID || "";
        let failure = null;
        for (const e of events) {
          if (e.sessionID && !sessionID) sessionID = e.sessionID;
          const part = e.part || {};
          if (part.type === "text" && typeof part.text === "string" && part.text.trim()) {
            text = part.text;
          } else if (part.type === "error" || e.error) {
            const em = (e.error && e.error.message) || (part.error && part.error.message);
            if (em) failure = em;
          }
        }

        if (failure) {
          return finish({ ok: false, text, error: failure, sessionID });
        }
        if (code !== 0) {
          const detail = String(stderr || "").trim() || `opencode exited with code ${code}${signal ? ` (${signal})` : ""}`;
          return finish({ ok: false, text, error: cut(detail, 400), sessionID });
        }
        if (!text.trim()) {
          return finish({ ok: false, text, error: "opencode didn't answer", sessionID });
        }
        finish({ ok: true, text, sessionID });
      }, 50);
    });
  });
}

/** Trim a long message down to something readable. */
function cut(s, n = 400) {
  const t = String(s == null ? "" : s).trim();
  return t.length > n ? `${t.slice(0, n)}…` : t;
}

/**
 * Pull a JSON object out of the reply — handles code fences, leading prose
 * and trailing chatter. Returns null when there is no JSON in there.
 */
function extractJson(text) {
  const t = String(text || "").trim();
  if (!t) return null;

  const fence = /```(?:json)?\s*([\s\S]*?)```/i.exec(t);
  const body = (fence ? fence[1] : t).trim();

  try {
    const v = JSON.parse(body);
    return v && typeof v === "object" ? v : null;
  } catch (_) {
    /* fall through to the brace scan */
  }

  // first balanced {...} block
  const start = body.indexOf("{");
  if (start === -1) return null;
  let depth = 0;
  let inStr = false;
  let esc = false;
  for (let i = start; i < body.length; i++) {
    const c = body[i];
    if (esc) {
      esc = false;
      continue;
    }
    if (c === "\\") {
      esc = true;
      continue;
    }
    if (c === '"') {
      inStr = !inStr;
      continue;
    }
    if (inStr) continue;
    if (c === "{") depth++;
    else if (c === "}") {
      depth--;
      if (depth === 0) {
        try {
          const v = JSON.parse(body.slice(start, i + 1));
          return v && typeof v === "object" ? v : null;
        } catch (_) {
          return null;
        }
      }
    }
  }
  return null;
}

/**
 * Ask opencode and expect JSON back.
 * Resolves {ok, data, text, error, sessionID} — never rejects.
 */
async function askJson(prompt, opts = {}) {
  const r = await ask(prompt, opts);
  if (!r.ok) return { ok: false, error: r.error, text: r.text, sessionID: r.sessionID };
  const data = extractJson(r.text);
  if (!data) {
    return {
      ok: false,
      error: "opencode's answer wasn't JSON",
      text: r.text,
      sessionID: r.sessionID,
    };
  }
  return { ok: true, data, text: r.text, sessionID: r.sessionID };
}

/** Is the opencode CLI actually usable here? */
function available() {
  return new Promise((resolve) => {
    const child = spawn(BIN, ["--version"], { stdio: ["ignore", "pipe", "ignore"] });
    let out = "";
    child.stdout.on("data", (d) => {
      out += d.toString();
    });
    child.on("error", () => resolve({ ok: false, version: "" }));
    child.on("exit", () => resolve({ ok: true, version: out.trim() }));
  });
}

module.exports = { ask, askJson, extractJson, available, BIN, AGENT, MODEL };
