/**
 * Laptop control from WhatsApp — owner-only remote for the machine this bot
 * runs on (X11 desktop, DISPLAY from the bot's own environment).
 *
 *   !task <request>           hand a free-form request to opencode and run it
 *   !cd [path]                change the working directory (relative paths work)
 *   !pwd                      show the working directory
 *   !open <path|url>          open a file, folder, app or URL
 *   !find <name>              locate files by name under $HOME
 *   !ls [path]                list a directory
 *   !play <query|path|url>    play audio/video (VLC for files, YouTube for queries)
 *   !yt [query]               search YouTube in the browser
 *   !pause / !resume / !next / !prev / !stop
 *                             media transport (playerctl, VLC fallback)
 *   !vol <0-150|up|down|mute> system volume
 *   !browser [query|url]      open/focus the browser and search or go to a URL
 *   !windows                  list open windows
 *   !focus <title>            raise a window by title
 *   !close <title>            close a window by title
 *   !key <combo>              send keys, e.g. "ctrl+t", "super+d", "Return"
 *   !type <text>              type text into the focused window
 *   !mouse <x> <y> [button]   click at screen coordinates
 *   !apps                     list launchable desktop apps
 *   !screen [n]               screenshot (monitor n, 1-based) and send it
 *   !lock                     lock the screen
 *   !sys                      battery / memory / disk / uptime at a glance
 *   !sh <command>             run a shell command
 *
 * Safety model (see README): every command is owner-only and logged with
 * sender and timestamp to control_audit.log. MISSION_CONTROL_DRY_RUN=1 prints
 * what would run without doing it.
 *
 * There are no confirmation prompts — the owner asked for the bot to just do
 * the thing. `!sh` and `!task` still get an automatic repair pass: if the
 * command fails, opencode is asked what went wrong, the corrected command is
 * retried, and the answer comes back working instead of as an error dump.
 *
 * Env:
 *   MISSION_OWNERS            comma-separated ids/lids allowed to control
 *                             (defaults to MISSION_OWNER + the check-in owner)
 *   MISSION_CONTROL_DRY_RUN   "1" → never actually execute
 *   MISSION_CONTROL_CWD       initial working directory (default $HOME)
 *   MISSION_BROWSER           browser binary for !browser/!yt (default brave)
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { exec, execFile } = require("child_process");
const { MessageMedia } = require("whatsapp-web.js");
require("dotenv").config();
const oc = require("./opencode");

const HOME = os.homedir();
const GROUP_ID = process.env.MISSION_GROUP_ID || "";
const API_URL = (process.env.MISSION_API_URL || "").replace(/\/+$/, "");
const AUDIT_FILE = path.join(__dirname, "..", "control_audit.log");
const STATE_FILE = path.join(__dirname, "..", "control_state.json");

const OWNERS = (process.env.MISSION_OWNERS || process.env.MISSION_OWNER || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

const DRY_RUN = String(process.env.MISSION_CONTROL_DRY_RUN || "") === "1";

/** How many times a failed command may be repaired and retried. */
const FIX_ATTEMPTS =
  Number(process.env.OPENCODE_FIX_ATTEMPTS) > 0
    ? Number(process.env.OPENCODE_FIX_ATTEMPTS)
    : 3;

/** Browser for !browser/!yt/!play searches. Brave by default, overridable. */
const BROWSER = process.env.MISSION_BROWSER || "brave-browser";

/** First candidate that actually exists on this machine. */
function resolveBrowser() {
  const candidates = [
    BROWSER,
    "brave-browser",
    "brave-browser-stable",
    "google-chrome",
    "chromium",
    "chromium-browser",
    "firefox",
  ];
  for (const c of candidates) {
    if (!c) continue;
    if (c.includes("/")) {
      try {
        if (fs.existsSync(c)) return c;
      } catch (_) {}
      continue;
    }
    const hit = (process.env.PATH || "")
      .split(":")
      .map((d) => path.join(d, c))
      .find((p) => {
        try {
          return fs.existsSync(p);
        } catch (_) {
          return false;
        }
      });
    if (hit) return hit;
  }
  return BROWSER; // last resort — let spawn report the failure
}

let browserBin = null;
function browser() {
  if (!browserBin) {
    browserBin = resolveBrowser();
    console.log(`[control] browser: ${browserBin}`);
  }
  return browserBin;
}

/** Open a URL in a new tab of the configured browser. */
function openUrl(url) {
  return launchSync(browser(), ["--new-tab", url]);
}

const CONFIRM_TTL_MS = 2 * 60 * 1000; // kept for compatibility; nothing waits for a confirmation now
const MAX_OUT = 3500; // reply length cap
const MEDIA_EXT = new Set([
  ".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv", ".wmv",
  ".mp3", ".m4a", ".aac", ".flac", ".wav", ".ogg", ".opus",
]);
const SKIP_DIRS = new Set([
  "node_modules", ".git", ".cache", ".local/share/Trash", "snap", ".npm",
  ".gradle", ".cargo", ".rustup", ".vscode-server", ".wwebjs_auth",
]);

// ---------------------------------------------------------------- helpers
const norm = (v) => {
  if (!v) return "";
  const id = typeof v === "object" ? v._serialized || v.id || "" : v;
  return String(id).split("@")[0].split(":")[0];
};

/** Single-quote a string for the shell (the safe way to interpolate text). */
const shq = (s) => `'${String(s == null ? "" : s).replace(/'/g, `'\\''`)}'`;

function isOwner(msg) {
  if (!OWNERS.length) return false; // no owners configured → nobody
  const raw = msg.author || msg.from || "";
  const candidate = norm(raw);
  return OWNERS.some((o) => norm(o) === candidate);
}

function audit(msg, line, ok = true) {
  const who = norm(msg && (msg.author || msg.from)) || "unknown";
  const entry = `${new Date().toISOString()}\t${ok ? "OK " : "ERR"}\t${who}\t${line}\n`;
  try {
    fs.appendFileSync(AUDIT_FILE, entry);
  } catch (_) {}
  console.log(`[control] ${entry.trim()}`);
}

const cut = (s, n = MAX_OUT) => {
  const t = String(s == null ? "" : s).trim();
  return t.length > n ? `${t.slice(0, n)}\n… (${t.length - n} more chars)` : t;
};

// ------------------------------------------------------- working directory
/**
 * The directory every path-ish command and every shell command runs in.
 * `!cd` moves it; it survives a restart because it lives in control_state.json.
 */
let cwd = process.env.MISSION_CONTROL_CWD || HOME;
let prevCwd = null;

function loadCwd() {
  try {
    const s = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
    if (s && typeof s.cwd === "string" && fs.existsSync(s.cwd)) cwd = s.cwd;
    if (s && typeof s.prev === "string" && fs.existsSync(s.prev)) prevCwd = s.prev;
  } catch (_) {
    /* first run — keep the default */
  }
}

function saveCwd() {
  try {
    fs.writeFileSync(
      STATE_FILE,
      JSON.stringify({ cwd, prev: prevCwd, at: new Date().toISOString() }, null, 2)
    );
  } catch (e) {
    console.error("[control] could not save cwd:", e.message);
  }
}

loadCwd();

/** The directory commands currently run in. */
function getCwd() {
  return cwd;
}

/**
 * Move the working directory.
 * Accepts an absolute path, a relative path, "..", "-" (previous) or "~".
 */
function setCwd(target) {
  const resolved = resolvePath(target);
  if (!resolved) return { ok: false, error: `No such directory: ${target}` };
  if (!fs.statSync(resolved).isDirectory()) {
    return { ok: false, error: `Not a directory: ${resolved}` };
  }
  prevCwd = cwd;
  cwd = resolved;
  saveCwd();
  return { ok: true, cwd };
}

/** Run a command; resolves {code, out} — never rejects. Runs in `cwd`. */
function run(cmd, opts = {}) {
  return new Promise((resolve) => {
    if (DRY_RUN) return resolve({ code: 0, out: `[dry-run] ${cmd}` });
    const { cwd: optCwd, timeout, ...rest } = opts;
    exec(
      cmd,
      {
        cwd: optCwd || cwd,
        timeout: timeout || 20000,
        maxBuffer: 4 * 1024 * 1024,
        ...rest,
      },
      (err, stdout, stderr) => {
        resolve({
          code: err && typeof err.code === "number" ? err.code : err ? 1 : 0,
          out: `${stdout || ""}${stderr || ""}`.trim() || (err ? err.message : ""),
        });
      }
    );
  });
}

/** Run a program with an argv array (no shell — safe for user text). */
function runFile(file, args, opts = {}) {
  return new Promise((resolve) => {
    if (DRY_RUN) return resolve({ code: 0, out: `[dry-run] ${file} ${args.join(" ")}` });
    const { cwd: optCwd, timeout, ...rest } = opts;
    execFile(
      file,
      args,
      {
        cwd: optCwd || cwd,
        timeout: timeout || 20000,
        maxBuffer: 4 * 1024 * 1024,
        ...rest,
      },
      (err, stdout, stderr) => {
        resolve({
          code: err && typeof err.code === "number" ? err.code : err ? 1 : 0,
          out: `${stdout || ""}${stderr || ""}`.trim() || (err ? err.message : ""),
        });
      }
    );
  });
}

/**
 * Detached spawn — for GUI apps that must outlive the request.
 * A missing binary or refused exec surfaces as an async 'error' event; we wait
 * one tick for it so callers can tell the user instead of reporting success.
 */
function launchSync(cmd, args = []) {
  if (DRY_RUN) return { pid: -1, dry: true, ok: true };
  const { spawn } = require("child_process");
  return new Promise((resolve) => {
    let settled = false;
    let child;
    try {
      child = spawn(cmd, args, {
        detached: true,
        stdio: "ignore",
        cwd,
        env: { ...process.env, DISPLAY: process.env.DISPLAY || ":0" },
      });
    } catch (e) {
      return resolve({ ok: false, error: e.message });
    }
    const onError = (e) => {
      if (settled) return;
      settled = true;
      resolve({ ok: false, error: e.code === "ENOENT" ? `no such program: ${cmd}` : e.message });
    };
    child.once("error", onError);
    // give the error event a chance to fire before declaring success
    setTimeout(() => {
      if (settled) return;
      settled = true;
      child.removeListener("error", onError);
      child.unref();
      resolve({ ok: true, pid: child.pid });
    }, 150);
  });
}

/**
 * Resolve a path the way the user means it:
 *   "~/x"  → under $HOME
 *   "."    → the working directory
 *   "-"    → the directory we came from
 *   "x/y"  → relative to the working directory
 */
function resolvePath(p) {
  let s = String(p == null ? "" : p).trim().replace(/^["']|["']$/g, "");
  if (!s || s === ".") return cwd;
  if (s === "-") return prevCwd || cwd;
  if (s === "~") return HOME;
  if (s.startsWith("~/")) s = path.join(HOME, s.slice(2));
  if (!path.isAbsolute(s)) s = path.join(cwd, s);
  return path.normalize(s);
}

/** Relative paths resolve against the working directory, not $HOME. */
function expandPath(p) {
  return resolvePath(p);
}

function human(bytes) {
  const u = ["B", "K", "M", "G", "T"];
  let n = Number(bytes) || 0;
  let i = 0;
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)}${u[i]}`;
}

// ---------------------------------------------------------------- app index
let appIndex = null; // [{name, exec, generic}]
let appIndexAt = 0;

/** Scan .desktop files so !apps and !open <app name> know what exists. */
async function buildAppIndex() {
  if (appIndex && Date.now() - appIndexAt < 10 * 60 * 1000) return appIndex;
  const dirs = [
    "/usr/share/applications",
    "/usr/local/share/applications",
    path.join(HOME, ".local/share/applications"),
    "/var/lib/flatpak/exports/share/applications",
  ].filter((d) => {
    try {
      return fs.statSync(d).isDirectory();
    } catch (_) {
      return false;
    }
  });

  const found = new Map();
  for (const dir of dirs) {
    let files = [];
    try {
      files = fs.readdirSync(dir).filter((f) => f.endsWith(".desktop"));
    } catch (_) {
      continue;
    }
    for (const f of files) {
      try {
        const text = fs.readFileSync(path.join(dir, f), "utf8");
        if (/^NoDisplay=true/m.test(text) || /^Hidden=true/m.test(text)) continue;
        const name = (/^Name=(.*)$/m.exec(text) || [])[1];
        const exec = (/^Exec=(.*)$/m.exec(text) || [])[1];
        const generic = (/^GenericName=(.*)$/m.exec(text) || [])[1] || "";
        if (!name || !exec) continue;
        const bin = exec.replace(/ ?%[fFuUdDnNickvm]/g, "").trim().split(/\s+/)[0];
        if (!bin) continue;
        // prefer the first entry per lowercase name
        const key = name.toLowerCase();
        if (!found.has(key)) found.set(key, { name, exec, generic, bin });
      } catch (_) {}
    }
  }
  appIndex = [...found.values()].sort((a, b) => a.name.localeCompare(b.name));
  appIndexAt = Date.now();
  return appIndex;
}

function findApp(index, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return null;
  const exe = (a) => a.exec.toLowerCase();
  return (
    index.find((a) => a.name.toLowerCase() === q) ||
    index.find((a) => exe(a).includes(q) || a.name.toLowerCase().includes(q)) ||
    (q.length >= 3 ? index.find((a) => a.generic.toLowerCase().includes(q)) : null)
  );
}

// ---------------------------------------------------------------- media
/** Direct D-Bus MPRIS call — VLC ignores playerctl but answers this. */
async function mprisCall(player, method) {
  return run(
    `dbus-send --print-reply --type=method_call --dest=org.mpris.MediaPlayer2.${player} ` +
      `/org/mpris/MediaPlayer2 org.mpris.MediaPlayer2.Player.${method} 2>&1`
  );
}

async function mprisGet(player, prop) {
  const r = await run(
    `dbus-send --print-reply --dest=org.mpris.MediaPlayer2.${player} ` +
      `/org/mpris/MediaPlayer2 org.freedesktop.DBus.Properties.Get ` +
      `string:org.mpris.MediaPlayer2.Player string:${prop} 2>&1`
  );
  const m = /string "(.*)"/.exec(r.out);
  return m ? m[1] : "";
}

/** Track title from an MPRIS player's Metadata dict (best effort). */
async function mprisTitle(player) {
  const r = await run(
    `dbus-send --print-reply --dest=org.mpris.MediaPlayer2.${player} ` +
      `/org/mpris/MediaPlayer2 org.freedesktop.DBus.Properties.Get ` +
      `string:org.mpris.MediaPlayer2.Player string:Metadata 2>&1`
  );
  const m = /string "xesam:title"\s+variant\s+string "(.*)"/.exec(r.out);
  return m ? m[1] : "";
}

/** Which MPRIS players are actually live right now. */
async function mprisPlayers() {
  const r = await run("dbus-send --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null");
  return [...r.out.matchAll(/org\.mpris\.MediaPlayer2\.([A-Za-z0-9_.]+)/g)].map((m) => m[1]);
}

/**
 * Media transport. VLC needs direct D-Bus (playerctl reports it as Stopped and
 * its calls don't land), so prefer whichever player we can actually see.
 */
async function mediaCtl(action) {
  const method = { pause: "PlayPause", resume: "Play", next: "Next", prev: "Previous", stop: "Stop" }[action] || "PlayPause";
  const players = await mprisPlayers();

  // VLC first when it's running — it's the usual video player here
  const vlcIdx = players.findIndex((p) => /^vlc/.test(p));
  if (vlcIdx !== -1) {
    const player = players[vlcIdx];
    const call = await mprisCall(player, method);
    const state = await mprisGet(player, "PlaybackStatus");
    const title = await mprisTitle(player);
    if (call.code === 0) {
      return { ok: true, how: `${player}/dbus`, state, now: title || "", players: players.length };
    }
  }

  // anything else (browser players) via playerctl
  const pc = await run(`playerctl ${method === "PlayPause" ? "play-pause" : method.toLowerCase()} 2>&1`);
  const state = (await run("playerctl status 2>/dev/null")).out.trim();
  const now = (await run("playerctl metadata xesam:title 2>/dev/null")).out.trim();
  if (pc.code === 0) return { ok: true, how: "playerctl", state, now, players: players.length };

  if (action === "stop") {
    const v = await run("pkill -f 'vlc' 2>&1");
    return { ok: v.code === 0, how: "vlc/kill", state: "Stopped", now };
  }
  return { ok: false, how: "none", detail: pc.out, players: players.length };
}

/** Turn a transport result into a truthful one-liner. */
function transportLine(icon, done, r) {
  const what = r.now ? ` — *${r.now}*` : "";
  const state = r.state ? ` (${r.state.toLowerCase()})` : "";
  if (!r.ok) return `⚠️ Couldn't ${done}${what}. ${cut(r.detail || "", 160)}`;
  if (!r.players && !r.now) return `⚠️ Nothing is playing right now.`;
  return `${icon} ${done}${what}${state}`;
}

/** Is a path something VLC should get rather than a browser? */
function looksLikeMedia(p) {
  if (/^https?:\/\//i.test(p) && /(youtube|youtu\.be|vimeo|\.mp4|\.mp3)/i.test(p)) return true;
  return MEDIA_EXT.has(path.extname(p).toLowerCase());
}

/** The owner's media folder — !hanuman and !others read from here. */
const LISTEN_DIR = path.join(HOME, "Desktop", "listen");

/** Media files directly inside LISTEN_DIR (no subfolders, no .srt). */
function listenFiles() {
  try {
    return fs
      .readdirSync(LISTEN_DIR)
      .filter((f) => MEDIA_EXT.has(path.extname(f).toLowerCase()))
      .sort()
      .map((f) => path.join(LISTEN_DIR, f));
  } catch (_) {
    return [];
  }
}

/**
 * Play one or more local files / direct URLs through VLC (detached, survives
 * the reply). opts.rate sets playback speed; opts.loop repeats the playlist.
 */
async function playMedia(target, opts = {}) {
  const files = (Array.isArray(target) ? target : [target]).map((t) =>
    /^https?:\/\//i.test(t) ? t : expandPath(t)
  );
  const args = ["--started-from-file"];
  if (opts.rate) args.push(`--rate=${opts.rate}`);
  if (opts.loop) args.push("--loop");
  args.push(...files);
  const res = await launchSync("vlc", args);
  return { ok: !!res.ok, arg: files.join(", "), files, pid: res.pid, dry: res.dry, error: res.error };
}

/** Query → YouTube results page in the configured browser. */
async function playYoutube(query) {
  const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(query)}`;
  const res = await openUrl(url);
  return { ok: !!res.ok, url, pid: res.pid, dry: res.dry, error: res.error };
}

// ---------------------------------------------------------------- windows
async function listWindows() {
  const r = await run("wmctrl -lx 2>/dev/null");
  if (r.code !== 0 || !r.out) return [];
  return r.out
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => {
      const parts = l.split(/\s+/);
      // 0xID desktop host class title…
      return { id: parts[0], desktop: parts[1], host: parts[2], klass: parts[3], title: parts.slice(4).join(" ") };
    })
    .filter((w) => w.desktop !== "-1");
}

function matchWindow(wins, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return null;
  return (
    wins.find((w) => w.title.toLowerCase() === q) ||
    wins.find((w) => w.title.toLowerCase().includes(q)) ||
    wins.find((w) => w.klass.toLowerCase().includes(q))
  );
}

// ---------------------------------------------------------------- opencode
/**
 * The bot doesn't try to guess what a free-form request means — opencode does.
 * It turns the request into one shell command (or picks one of the bot's own
 * commands), and when a command fails it works out the fix.
 */

const BOT_COMMANDS = [
  "open", "find", "ls", "play", "yt", "pause", "resume", "next", "prev",
  "stop", "vol", "browser", "windows", "focus", "close", "key", "type",
  "mouse", "apps", "screen", "lock", "sys", "hanuman", "others",
];

const TASK_PROMPT = (request, dir) => `You plan shell commands for a WhatsApp bot that controls a Linux laptop.

Working directory: ${dir}

The user asked for:
${request}

Reply with ONE JSON object and nothing else — no prose, no markdown fences:
{"command":"<one shell command>","why":"<max 6 words>"}

OR, when one of the bot's own commands does the job better, reply with:
{"bot_command":"<one of: ${BOT_COMMANDS.join(", ")}>","arg":"<arguments>"}

Rules:
- The command runs under bash in the working directory above; relative paths are fine.
- Chain steps with && if you need more than one.
- Stick to tools that exist on this box: ls, cat, grep, find, du, df, ps, git, python3, wc, head, tail.
- Read-only unless the user clearly wants files changed.
- Never produce rm -rf, mkfs, dd or shutdown.`;

const FIX_PROMPT = (cmd, dir, code, out) => `A shell command failed on a Linux box. Work out the corrected command.

Working directory: ${dir}
Command: ${cmd}
Exit code: ${code}
Output:
${out}

Reply with ONE JSON object and nothing else — no prose, no markdown fences:
{"command":"<corrected command>","why":"<max 6 words>"}

Rules:
- Keep the intent of the original command exactly the same. Only repair the technical problem: a wrong path, a missing flag, a wrong tool name, wrong syntax, a missing permission.
- Never swap in a different command that does something else.
- If the original command cannot work as intended (the path really does not exist, the service really is not running), repeat it unchanged — the caller will report the real problem.`;

const GIVEUP_PROMPT = (cmd, dir, code, out) => `This command still won't work.

Working directory: ${dir}
Command: ${cmd}
Exit code: ${code}
Output:
${out}

Tell the user, in plain words, what went wrong and what to do instead.
Reply with ONE JSON object and nothing else — no prose, no markdown fences:
{"answer":"<2-4 short sentences>","command":"<a command that would work, or empty>"}`;

/**
 * Run a command and, if it fails, ask opencode what went wrong and retry the
 * corrected command. Returns {ok, cmd, out, code, tries, fixed}.
 */
async function runWithFix(cmd, dir, opts = {}) {
  let current = String(cmd || "").trim();
  let sessionID = "";
  let last = null;
  const max = FIX_ATTEMPTS;

  for (let i = 0; i <= max; i++) {
    const r = await run(current, { cwd: dir, timeout: opts.timeout || 60000 });
    last = { code: r.code, out: r.out, cmd: current };
    if (r.code === 0) {
      return { ok: true, cmd: current, out: r.out, code: 0, tries: i, fixed: i > 0, sessionID };
    }
    if (i === max) break;
    console.log(`[control] command failed (${r.code}) — asking opencode for a fix: ${current}`);
    const fix = await oc.askJson(FIX_PROMPT(current, dir, r.code, cut(r.out, 2000)), {
      cwd: dir,
      sessionID,
    });
    if (!fix.ok) {
      return {
        ok: false, cmd: current, out: r.out, code: r.code, tries: i, fixed: false,
        error: fix.error, sessionID,
      };
    }
    sessionID = fix.sessionID || sessionID;
    const next = String((fix.data && fix.data.command) || "").trim();
    if (!next || next === current) {
      return { ok: false, cmd: current, out: r.out, code: r.code, tries: i, fixed: false, sessionID };
    }
    current = next;
  }
  return {
    ok: false, cmd: last.cmd, out: last.out, code: last.code,
    tries: max, fixed: false, sessionID,
  };
}

/**
 * Last resort: ask opencode to explain the failure in words the user can act on.
 * Never throws.
 */
async function explainFailure(res, dir) {
  try {
    const r = await oc.askJson(
      GIVEUP_PROMPT(res.cmd, dir, res.code, cut(res.out, 1500)),
      { cwd: dir, sessionID: res.sessionID }
    );
    if (!r.ok) return "";
    const answer = String((r.data && r.data.answer) || "").trim();
    const cmd = String((r.data && r.data.command) || "").trim();
    if (cmd && cmd !== res.cmd) {
      const again = await run(cmd, { cwd: dir, timeout: 60000 });
      if (again.code === 0) {
        return `${answer}\n\n$ ${cmd}\n${cut(again.out, 2000) || "(no output)"}`;
      }
    }
    return answer;
  } catch (_) {
    return "";
  }
}

/** Format a command + its output for WhatsApp. */
function cmdBlock(cmd, out) {
  return `$ ${cmd}\n${cut(out, 2800) || "(no output)"}`;
}

// ---------------------------------------------------------------- commands
const commands = {
  async apps() {
    const idx = await buildAppIndex();
    const lines = idx.slice(0, 40).map((a) => `• ${a.name}`);
    return {
      text: `*${idx.length} apps found*\n${lines.join("\n")}${idx.length > 40 ? `\n… +${idx.length - 40} more` : ""}`,
    };
  },

  async open(arg) {
    if (!arg) return { text: "Usage: `!open <file|folder|app|url>`" };
    if (/^https?:\/\//i.test(arg)) {
      const r = await openUrl(arg);
      if (!r.ok) return { text: `⚠️ Couldn't open the browser: ${r.error || "unknown error"}` };
      return { text: `🌐 Opening ${arg}` };
    }
    const p = expandPath(arg);
    if (fs.existsSync(p)) {
      if (looksLikeMedia(p)) {
        const r = await playMedia(p);
        if (!r.ok) return { text: `⚠️ Couldn't open VLC for \`${p}\`: ${r.error || "unknown error"}` };
        return { text: `🎬 Playing in VLC: ${p}` };
      }
      const r = await launchSync("xdg-open", [p]);
      if (!r.ok) return { text: `⚠️ Couldn't open \`${p}\`: ${r.error || "unknown error"}` };
      const kind = fs.statSync(p).isDirectory() ? "📁" : "📄";
      return { text: `${kind} Opened ${p}` };
    }
    // not a path — maybe an app name
    const idx = await buildAppIndex();
    const app = findApp(idx, arg);
    if (app) {
      const r = await launchSync(app.bin, []);
      if (!r.ok) return { text: `⚠️ Couldn't launch *${app.name}* (${app.bin}): ${r.error || "unknown error"}` };
      return { text: `🚀 Launched *${app.name}* (${app.bin})` };
    }
    return { text: `Nothing at \`${p}\` and no app matching *${arg}*. Try \`!apps\`.` };
  },

  async find(arg) {
    if (!arg) return { text: "Usage: `!find <name>`" };
    const q = String(arg).replace(/[*?\[\]]/g, ""); // glob chars would break the pattern
    if (!q) return { text: "Usage: `!find <name>`" };
    const skip = [...SKIP_DIRS].map((d) => `-path ${shq(`*/${d}/*`)} -prune -o`).join(" ");
    const cmd = `find ${shq(HOME)} ${skip} -iname ${shq(`*${q}*`)} -print 2>/dev/null | head -25`;
    const r = await run(cmd, { timeout: 45000 });
    const hits = r.out.split("\n").filter(Boolean);
    if (!hits.length) return { text: `No files matching *${arg}* under ${HOME}.` };
    return { text: `*${hits.length}${hits.length === 25 ? "+" : ""} matches*\n${hits.map((h) => `• ${h}`).join("\n")}` };
  },

  async ls(arg) {
    const p = expandPath(arg);
    if (!fs.existsSync(p)) return { text: `No such path: ${p}` };
    const entries = fs.readdirSync(p, { withFileTypes: true }).slice(0, 60);
    const lines = entries.map((e) => `${e.isDirectory() ? "📁" : "📄"} ${e.name}`);
    return { text: `*${p}* (${entries.length} shown)\n${lines.join("\n") || "(empty)"}` };
  },

  async play(arg) {
    if (!arg) return { text: "Usage: `!play <file|url|search>`" };
    if (looksLikeMedia(arg) && (/^https?:\/\//i.test(arg) || fs.existsSync(expandPath(arg)))) {
      const r = await playMedia(arg);
      if (!r.ok) return { text: `⚠️ Couldn't play \`${r.arg}\`: ${r.error || "unknown error"}` };
      return { text: `🎬 Playing in VLC: ${r.arg}` };
    }
    const r = await playYoutube(arg);
    if (!r.ok) return { text: `⚠️ Couldn't open the browser: ${r.error || "unknown error"}` };
    return { text: `▶️ Searching YouTube for *${arg}*` };
  },

  /** Hanuman Chalisa from ~/Desktop/listen at 1.5×, looping until !stop. */
  async hanuman() {
    const file = listenFiles().find((f) => /hanuman|chalisa/i.test(path.basename(f)));
    if (!file) return { text: `⚠️ No Hanuman Chalisa file in ${LISTEN_DIR}.` };
    const r = await playMedia(file, { rate: 1.5, loop: true });
    if (!r.ok) return { text: `⚠️ Couldn't play \`${file}\`: ${r.error || "unknown error"}` };
    return { text: "🙏 Hanuman Chalisa at 1.5× — looping until `!stop`." };
  },

  /** Every other media file in ~/Desktop/listen, as one looping VLC playlist. */
  async others() {
    const files = listenFiles().filter((f) => !/hanuman|chalisa/i.test(path.basename(f)));
    if (!files.length) return { text: `⚠️ No other media files in ${LISTEN_DIR}.` };
    const r = await playMedia(files, { loop: true });
    if (!r.ok) return { text: `⚠️ Couldn't play the other files: ${r.error || "unknown error"}` };
    return {
      text:
        `🎬 Looping ${files.length} file(s) from ${LISTEN_DIR}:\n` +
        files.map((f) => `• ${path.basename(f)}`).join("\n"),
    };
  },

  async yt(arg) {
    if (!arg) {
      const r = await openUrl("https://www.youtube.com");
      if (!r.ok) return { text: `⚠️ Couldn't open the browser: ${r.error || "unknown error"}` };
      return { text: "▶️ Opening YouTube" };
    }
    const r = await playYoutube(arg);
    if (!r.ok) return { text: `⚠️ Couldn't open the browser: ${r.error || "unknown error"}` };
    return { text: `▶️ YouTube: *${arg}*` };
  },

  async pause() {
    const r = await mediaCtl("pause");
    return { text: transportLine("⏸️", "Paused", r) };
  },
  async resume() {
    const r = await mediaCtl("resume");
    return { text: transportLine("▶️", "Resumed", r) };
  },
  async next() {
    const r = await mediaCtl("next");
    return { text: transportLine("⏭️", "Skipped", r) };
  },
  async prev() {
    const r = await mediaCtl("prev");
    return { text: transportLine("⏮️", "Went back", r) };
  },
  async stop() {
    const r = await mediaCtl("stop");
    return { text: transportLine("⏹️", "Stopped", r) };
  },

  async vol(arg) {
    const a = String(arg || "").trim().toLowerCase();
    if (!a) {
      const r = await run("pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null; pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null");
      if (!r.out) return { text: "⚠️ Couldn't read the volume (no audio sink? is `pactl` available?)." };
      return { text: `🔊 ${cut(r.out.replace(/\s+/g, " "), 200)}` };
    }
    if (a === "mute" || a === "unmute" || a === "toggle") {
      const r = await run(`pactl set-sink-mute @DEFAULT_SINK@ ${a === "toggle" ? "toggle" : a === "mute" ? "1" : "0"} 2>&1`);
      return { text: r.code === 0 ? `🔇 Volume ${a}.` : `⚠️ Couldn't ${a} the volume: ${cut(r.out, 150)}` };
    }
    if (a === "up" || a === "down") {
      const r = await run(`pactl set-sink-volume @DEFAULT_SINK@ ${a === "up" ? "+10%" : "-10%"} 2>&1`);
      return { text: r.code === 0 ? `🔊 Volume ${a} 10%.` : `⚠️ Couldn't change the volume: ${cut(r.out, 150)}` };
    }
    const n = Number(a.replace("%", ""));
    if (!Number.isFinite(n) || n < 0 || n > 150) return { text: "Usage: `!vol <0-150|up|down|mute>`" };
    const r = await run(`pactl set-sink-volume @DEFAULT_SINK@ ${n}% 2>&1`);
    return { text: r.code === 0 ? `🔊 Volume set to ${n}%.` : `⚠️ Couldn't set the volume: ${cut(r.out, 150)}` };
  },

  async browser(arg) {
    const fail = (r) => ({ text: `⚠️ Couldn't open the browser: ${r.error || "unknown error"}` });
    if (arg && /^https?:\/\//i.test(arg)) {
      const r = await openUrl(arg);
      if (!r.ok) return fail(r);
      return { text: `🌐 ${arg}` };
    }
    const q = arg || "";
    const url = q
      ? `https://www.google.com/search?q=${encodeURIComponent(q)}`
      : "https://www.google.com";
    const r = await openUrl(url);
    if (!r.ok) return fail(r);
    return { text: q ? `🔎 Searching the web for *${q}*` : "🌐 Opening the browser" };
  },

  async windows() {
    const wins = await listWindows();
    if (!wins.length) return { text: "No windows listed (`wmctrl` found none)." };
    return {
      text: `*${wins.length} windows*\n${wins.map((w) => `• ${w.title || "(untitled)"}  —  _${w.klass}_`).join("\n")}`,
    };
  },

  async focus(arg) {
    const wins = await listWindows();
    const w = matchWindow(wins, arg);
    if (!w) return { text: `No window matches *${arg}*. Try \`!windows\`.` };
    const r = await run(`wmctrl -ia ${w.id}`);
    return { text: r.code === 0 ? `🪟 Focused: ${w.title}` : `Couldn't focus it. ${cut(r.out, 150)}` };
  },

  async close(arg) {
    const wins = await listWindows();
    const w = matchWindow(wins, arg);
    if (!w) return { text: `No window matches *${arg}*. Try \`!windows\`.` };
    const r = await run(`wmctrl -ic ${w.id}`);
    return { text: r.code === 0 ? `🪟 Closed: ${w.title}` : `Couldn't close it. ${cut(r.out, 150)}` };
  },

  async key(arg) {
    if (!arg) return { text: "Usage: `!key <combo>` — e.g. `ctrl+t`, `super+d`, `Return`" };
    const r = await runFile("xdotool", ["key", "--clearmodifiers", arg]);
    return { text: r.code === 0 ? `⌨️ Sent \`${arg}\`` : `xdotool failed: ${cut(r.out, 200)}` };
  },

  async type(arg) {
    if (!arg) return { text: "Usage: `!type <text>`" };
    const r = await runFile("xdotool", ["type", "--clearmodifiers", "--delay", "25", arg]);
    return { text: r.code === 0 ? `⌨️ Typed ${arg.length} chars.` : `xdotool failed: ${cut(r.out, 200)}` };
  },

  async mouse(arg) {
    const parts = String(arg || "").trim().split(/\s+/);
    const x = Number(parts[0]);
    const y = Number(parts[1]);
    if (!Number.isFinite(x) || !Number.isFinite(y)) return { text: "Usage: `!mouse <x> <y> [1|2|3]`" };
    const btn = Number(parts[2]) || 1;
    const mv = await runFile("xdotool", ["mousemove", String(x), String(y)]);
    if (mv.code !== 0) return { text: `xdotool failed: ${cut(mv.out, 200)}` };
    const cl = await runFile("xdotool", ["click", String(btn)]);
    return { text: cl.code === 0 ? `🖱️ Clicked ${btn} at (${x}, ${y}).` : `Click failed: ${cut(cl.out, 200)}` };
  },

  async screen(arg) {
    const out = path.join(os.tmpdir(), `mission-screen-${Date.now()}.png`);
    let r = await runFile("gnome-screenshot", ["-f", out]);
    if (r.code !== 0 || !fs.existsSync(out)) {
      r = await runFile("import", ["-window", "root", out]);
    }
    if (!fs.existsSync(out)) {
      return { text: `⚠️ Screenshot failed: ${cut(r.out, 200) || "no screenshot tool available"}` };
    }
    let media;
    try {
      media = MessageMedia.fromFilePath(out);
    } catch (e) {
      return { text: `⚠️ Screenshot taken but couldn't be attached: ${cut(e.message, 200)}` };
    }
    setTimeout(() => {
      try {
        fs.unlinkSync(out);
      } catch (_) {}
    }, 30000);
    return { media, text: "🖥️ Screenshot" };
  },

  async lock() {
    const tries = [
      "loginctl lock-session",
      "xdg-screensaver lock",
      "gnome-screensaver-command -l",
    ];
    for (const c of tries) {
      const r = await run(`${c} 2>&1`);
      if (r.code === 0) return { text: "🔒 Screen locked." };
    }
    return { text: "Couldn't lock the screen (no supported locker found)." };
  },

  async sys() {
    const [bat, mem, disk, up, load] = await Promise.all([
      run("cat /sys/class/power_supply/BAT*/capacity 2>/dev/null | head -1"),
      run("free -h | awk 'NR==2{print $3\" used / \"$2}'"),
      run(`df -h ${HOME} | awk 'NR==2{print $3\" used / \"$2\" (\"$5\")\"}'`),
      run("uptime -p"),
      run("cat /proc/loadavg"),
    ]);
    return {
      text:
        `*Machine*\n` +
        `🔋 Battery: ${bat.out || "n/a"}\n` +
        `🧠 Memory: ${mem.out || "n/a"}\n` +
        `💾 Disk ($HOME): ${disk.out || "n/a"}\n` +
        `⏱️ Uptime: ${up.out || "n/a"}\n` +
        `📈 Load: ${cut(load.out, 60)}` +
        (DRY_RUN ? "\n\n⚠️ _dry-run mode is ON_" : ""),
    };
  },

  async sh(arg) {
    if (!arg) return { text: "Usage: `!sh <command>`" };
    const dir = getCwd();
    const res = await runWithFix(arg, dir, { timeout: 30000 });
    if (res.ok) {
      const head = res.fixed
        ? `_that failed first, so I fixed it and ran this:_\n`
        : "";
      return { text: `${head}${cmdBlock(res.cmd, res.out)}` };
    }
    const why = await explainFailure(res, dir);
    return {
      text:
        `⚠️ *That didn't work* (exit ${res.code})\n\n${cmdBlock(res.cmd, res.out)}` +
        (why ? `\n\n${why}` : ""),
    };
  },

  /** Move the working directory — every later command runs here. */
  async cd(arg) {
    const raw = String(arg || "").trim();
    const res = setCwd(raw || "~");
    if (!res.ok) return { text: `⚠️ ${res.error}` };
    let entries = [];
    try {
      entries = fs.readdirSync(res.cwd, { withFileTypes: true }).slice(0, 15);
    } catch (_) {}
    const lines = entries.map((e) => `${e.isDirectory() ? "📁" : "📄"} ${e.name}`);
    return { text: `📂 *${res.cwd}*\n${lines.join("\n") || "(empty)"}` };
  },

  /** Where am I? */
  async pwd() {
    return { text: `📂 ${getCwd()}` };
  },

  /**
   * A free-form request, handed to opencode. opencode decides what to run
   * (or which bot command to use); the bot runs it and, if it fails, lets
   * opencode work out the fix before retrying.
   */
  async task(arg, client, msg) {
    const request = String(arg || "").trim();
    if (!request) {
      return {
        text:
          "Usage: `!task <what you want>`\n" +
          "e.g. `!task show me the 5 biggest folders here`",
      };
    }
    const dir = getCwd();

    // A nudge if opencode takes a while — not a confirmation, just "still on it".
    const nudge = setTimeout(() => {
      reply(msg, "🧠 Working on it…").catch(() => {});
    }, 8000);

    let plan;
    try {
      plan = await oc.askJson(TASK_PROMPT(request, dir), { cwd: dir });
    } catch (e) {
      clearTimeout(nudge);
      return { text: `⚠️ opencode didn't answer: ${cut(e.message, 200)}` };
    }

    try {
      if (!plan.ok) {
        return {
          text:
            `⚠️ opencode couldn't work out that one: ${cut(plan.error, 250)}\n\n` +
            "Try `!sh <command>` instead.",
        };
      }
      const data = plan.data || {};

      // opencode picked one of the bot's own commands
      const botCmd = String(data.bot_command || "").trim().toLowerCase();
      if (botCmd && commands[botCmd]) {
        const extra = String(data.arg || "").trim();
        const res = asResult(await commands[botCmd](extra, client, msg));
        return res;
      }

      const cmd = String(data.command || "").trim();
      if (!cmd) {
        const why = String(data.why || plan.text || "").trim();
        return { text: `🤔 ${cut(why, 900)}` };
      }

      const res = await runWithFix(cmd, dir, { timeout: 60000 });
      if (res.ok) {
        const head = res.fixed
          ? `_first try failed — this is what worked:_\n`
          : String(data.why || "").trim()
          ? `_${String(data.why).trim()}_\n`
          : "";
        return { text: `${head}${cmdBlock(res.cmd, res.out)}` };
      }
      const why = await explainFailure(res, dir);
      return {
        text:
          `⚠️ *Couldn't do that* (exit ${res.code})\n\n${cmdBlock(res.cmd, res.out)}` +
          (why ? `\n\n${why}` : ""),
      };
    } finally {
      clearTimeout(nudge);
    }
  },
};

// Friendly aliases: !chalisa and !listen do the same as !hanuman / !others.
commands.chalisa = commands.hanuman;
commands.listen = commands.others;

// ---------------------------------------------------------------- results
/** Every command must answer with {text, media?}; tolerate a bare string. */
function asResult(res) {
  // A command that returns nothing almost always means it silently bailed —
  // say so instead of implying success with an empty reply.
  const empty = "⚠️ Something went wrong — the command returned no result.";
  if (res == null) return { text: empty };
  if (typeof res === "string") return { text: res || empty };
  if (res.text == null && !res.media) return { text: empty };
  return res;
}

// ---------------------------------------------------------------- reply
const SEND_FAIL = "⚠️ Something went wrong — I couldn't send the reply.";

/**
 * Send a result back to the chat. Never throws: if WhatsApp rejects the first
 * attempt we retry as plain text, and if *that* fails we log it loudly so the
 * failure is visible in the console rather than silently swallowed.
 */
async function reply(msg, text, media) {
  const send = async (payload) => {
    if (typeof msg.reply === "function") await msg.reply(payload, null, {});
    else await msg.client.sendMessage(msg.from, payload);
  };

  if (media) {
    // Replying-with-media trips a WhatsApp-web.js memoisation bug ("Data passed
    // to getter must include an id property"), so attach by sendMessage.
    try {
      await msg.client.sendMessage(msg.from, media, { caption: text });
      return;
    } catch (e) {
      console.error("[control] media send failed:", e.message);
      try {
        await send(`${text}\n(⚠️ Couldn't attach the file: ${e.message})`);
        return;
      } catch (e2) {
        console.error("[control] text fallback after media failure also failed:", e2.message);
        return;
      }
    }
  }

  try {
    await send(text);
  } catch (e) {
    console.error("[control] reply failed:", e.message);
    // last resort: a bare message with no quoting
    try {
      await msg.client.sendMessage(msg.from, SEND_FAIL);
    } catch (e2) {
      console.error("[control] could not deliver any reply:", e2.message);
    }
  }
}

// ---------------------------------------------------------------- entry
const HELP =
  "*Laptop control* (owner only)\n" +
  "`!task <request>` · ask opencode to do it\n" +
  "`!cd [path]` · `!pwd` · move the working directory\n" +
  "`!open <path|app|url>` · `!find <name>` · `!ls [path]`\n" +
  "`!play <file|url|search>` · `!yt [query]` · `!pause` `!resume` `!next` `!prev` `!stop`\n" +
  "`!hanuman` · Chalisa 1.5× on loop · `!others` · rest of ~/Desktop/listen on loop\n" +
  "`!vol <0-150|up|down|mute>` · `!browser [query|url]`\n" +
  "`!windows` · `!focus <title>` · `!close <title>`\n" +
  "`!key <combo>` · `!type <text>` · `!mouse <x> <y>`\n" +
  "`!apps` · `!screen` · `!lock` · `!sys` · `!sh <cmd>`\n" +
  "No confirmations — it just does it.";

/**
 * Handle one message. Returns true when it was a control command.
 * Everything is owner-gated and audited. No confirmation prompts: the owner
 * asked for the bot to just get on with it.
 */
async function handle(client, msg) {
  const body = String(msg.body || "").trim();
  if (!body.startsWith("!")) return false;

  const parts = body.slice(1).split(/\s+/);
  const cmd = (parts[0] || "").toLowerCase();
  const arg = parts.slice(1).join(" ");

  // doorbells that don't need owner rights
  if (cmd === "owner" || cmd === "whoami") {
    const me = norm(msg.author || msg.from);
    const ok = isOwner(msg);
    await reply(msg, ok ? `✅ You (${me}) can control this laptop.` : `🚫 ${me} is not on the owner list.`);
    return true;
  }

  if (cmd === "help") return false; // let the main !help answer

  if (!commands[cmd] && cmd !== "control") return false;

  if (!isOwner(msg)) {
    audit(msg, body, false);
    await reply(msg, "🚫 Not authorised — only the owner can control this laptop.");
    return true;
  }

  if (cmd === "control") {
    await reply(msg, HELP);
    return true;
  }

  audit(msg, `${cmd} ${arg}`);
  try {
    const res = asResult(await commands[cmd](arg, client, msg));
    await reply(msg, res.text, res.media);
  } catch (e) {
    audit(msg, `${cmd} ${arg} → ${e.message}`, false);
    await reply(msg, `⚠️ \`${cmd}\` failed: ${cut(e.message, 300)}`);
  }
  return true;
}

module.exports = {
  handle,
  isOwner,
  commands,
  HELP,
  OWNERS,
  DRY_RUN,
  expandPath,
  resolvePath,
  looksLikeMedia,
  norm,
  getCwd,
  setCwd,
  getPending: () => null,
  _setOwners(list) {
    OWNERS.length = 0;
    OWNERS.push(...list);
  },
};
