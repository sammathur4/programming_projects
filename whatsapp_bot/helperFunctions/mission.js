/**
 * Mission 2026 — WhatsApp daily check-in bridge.
 *
 * Talks to the Django backend (Mission 2026 README → "WhatsApp daily check-in
 * (two-way sync)"):
 *
 *   8 PM    one plain message per habit, sent ONE BY ONE — answering the
 *           current one (reply "done"/"missed", ✅/❌, or just typing it while
 *           it's pending) records the answer and sends the next habit.
 *           After MISSION_REMINDER_MS (default 5 min) of silence a reminder
 *           quoting the item goes out; MISSION_PROCEED_MS (default 10 min)
 *           after the item, the chain moves on so nothing stalls — late
 *           replies still count any time today.
 *   all day answers are POSTed to /api/mission/checkins/
 *   22:00   interim recap with a per-person progress bar
 *   23:55   final recap + 30-day leaderboard streaks
 *
 * Commands (any chat):
 *   !mission                 today's status for the sender
 *   !mission done <habit>    mark a habit done
 *   !mission missed <habit>  mark a habit missed
 *   !mission habits          list today's habits (with their keys)
 *
 * Env:
 *   MISSION_GROUP_ID    group the check-ins belong to ("...@g.us")
 *   MISSION_API_URL     API root, e.g. http://localhost:8000/api
 *   MISSION_API_KEY     optional shared secret → X-API-Key header
 *
 * Habit keys are slugs of the habit name and MUST match the backend's
 * habit_key() ('5L Water' → '5l_water').
 */
const fs = require("fs");
const path = require("path");
const axios = require("axios");
require("dotenv").config();

const GROUP_ID = process.env.MISSION_GROUP_ID || "";
const API_URL = (process.env.MISSION_API_URL || "").replace(/\/+$/, "");
const API_KEY = process.env.MISSION_API_KEY || "";
const STATE_FILE = path.join(__dirname, "..", "mission_state.json");

const MORNING_CRON = process.env.MISSION_MORNING_CRON || "0 20 * * *"; // 8 PM daily
const INTERIM_CRON = process.env.MISSION_INTERIM_CRON || "0 22 * * *";
const FINAL_CRON = process.env.MISSION_FINAL_CRON || "55 23 * * *";

/** No answer for this long → one reminder. Twice as long → move on. */
const REMINDER_MS = Number(process.env.MISSION_REMINDER_MS) > 0
  ? Number(process.env.MISSION_REMINDER_MS)
  : 5 * 60 * 1000;
const PROCEED_MS = Number(process.env.MISSION_PROCEED_MS) > 0
  ? Number(process.env.MISSION_PROCEED_MS)
  : 10 * 60 * 1000;

const BAR = 12;

const API = axios.create({
  baseURL: API_URL,
  timeout: 15000,
  headers: API_KEY ? { "X-API-Key": API_KEY } : {},
});

// ---------------------------------------------------------------- state
// { date, items: {msgId: habitKey}  ← today's plain check-in messages,
//   chain: {date, index, msgId, done} | null  ← one-by-one send position,
//   members: {extId: {name, wid, done: [], missed: []}}, dirty: [extId] }
let state = { date: "", items: {}, chain: null, members: {}, dirty: [] };
let seededOn = "";

/** In-memory view of the running chain (timers can't be persisted). */
// { client, habits, index, key, name, msgId, settled, pendingBody,
//   reminderTimer, proceedTimer }
let chain = null;

function loadState() {
  try {
    const parsed = JSON.parse(fs.readFileSync(STATE_FILE, "utf8"));
    if (parsed && typeof parsed === "object") {
      state = {
        date: parsed.date || "",
        items: parsed.items || {},
        chain: parsed.chain || null,
        members: parsed.members || {},
        dirty: parsed.dirty || [],
      };
    }
  } catch (_) {
    /* first run / unreadable — start fresh */
  }
}

function save() {
  try {
    fs.writeFileSync(STATE_FILE, JSON.stringify(state));
  } catch (e) {
    console.error("[mission] could not save state:", e.message);
  }
}

loadState();

/** Today as YYYY-MM-DD in the bot's local timezone (cron runs the same one). */
function today() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function delay(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

/**
 * '5L Water' -> '5l_water' — identical to the backend's habit_key():
 * non-alphanumerics become '_', runs collapse, edges strip.
 */
function slug(name) {
  let key = "";
  for (const c of String(name || "").toLowerCase()) {
    key += /[\p{L}\p{N}]/u.test(c) ? c : "_";
  }
  while (key.includes("__")) key = key.replace(/__/g, "_");
  return key.replace(/^_+|_+$/g, "");
}

/** "0 7 * * *" -> "7:00 AM" (for recap wording; falls back if unparseable). */
function cronLabel(cron, fallback) {
  const m = /^(\d{1,2}) (\d{1,2}) \* \* \*$/.exec(String(cron).trim());
  if (!m) return fallback;
  const min = m[1].padStart(2, "0");
  let h = Number(m[2]);
  const ap = h >= 12 ? "PM" : "AM";
  h = h % 12 || 12;
  return `${h}:${min} ${ap}`;
}

function bar(done, total) {
  const filled = total > 0 ? Math.round((done / total) * BAR) : 0;
  return "█".repeat(Math.max(0, Math.min(BAR, filled))) + "░".repeat(BAR - Math.max(0, Math.min(BAR, filled)));
}

/** "9199999999@c.us" / "1234567@lid" / "12345:2@c.us" -> bare id. */
function normalizeId(raw) {
  if (!raw) return "";
  const id = typeof raw === "object" ? raw._serialized || raw.id || "" : raw;
  return String(id).split("@")[0].split(":")[0];
}

function widen(raw) {
  if (!raw) return "";
  const id = typeof raw === "object" ? raw._serialized || raw.id || "" : raw;
  return String(id);
}

// ---------------------------------------------------------------- API
async function getHabits() {
  const { data } = await API.get("/habits/", { params: { status: "active" } });
  return data
    .filter((h) => h.active !== false && !h.is_paused)
    .map((h) => ({
      key: slug(h.name),
      // collapse stray double spaces so messages read cleanly
      name: String(h.name || "").replace(/\s+/g, " ").trim(),
      emoji: h.emoji || "✅",
      id: h.id,
    }));
}

async function getCheckins(date = today()) {
  const { data } = await API.get("/mission/checkins/", { params: { date } });
  return data;
}

/**
 * Today's per-habit rows from HabitLog — the *same* table the Flutter app reads.
 * This is the single source of truth: whatever the app shows, the bot shows.
 * Returns [{habit, status, done}] for the date.
 */
async function getHabitLogs(date = today()) {
  const { data } = await API.get("/habit-logs/", { params: { from: date, to: date } });
  return Array.isArray(data) ? data : [];
}

/**
 * The owner's completion state for a date, taken from HabitLog and expressed in
 * the bot's habit keys, so the bot and the app can never disagree.
 * Returns {done: [keys], missed: [keys], in_progress: [keys]} — status
 * "skipped" counts as missed, "in_progress" is its own bucket.
 */
async function logAnswers(habits, date = today()) {
  const logs = await getHabitLogs(date);
  const byId = new Map(logs.map((l) => [String(l.habit), l]));
  const done = [];
  const missed = [];
  const inProgress = [];
  const pending = [];
  for (const h of habits) {
    const row = byId.get(String(h.id));
    if (!row) continue;
    if (row.done || row.status === "done") done.push(h.key);
    else if (row.status === "skipped") missed.push(h.key);
    else if (row.status === "in_progress") inProgress.push(h.key);
    else if (row.status === "pending") pending.push(h.key);
  }
  return { done, missed, in_progress: inProgress, pending };
}

/**
 * One member's check-in straight from the API — the source of truth.
 * Returns {done, missed, in_progress, name} or null when nothing is logged.
 */
async function getMemberCheckin(member, date = today()) {
  const rows = await getCheckins(date);
  const row = (rows || []).find((r) => String(r.member) === String(member));
  if (!row) return null;
  return {
    member: String(row.member),
    name: row.name || "",
    whatsapp_id: row.whatsapp_id || "",
    done: row.done || [],
    missed: row.missed || [],
    in_progress: row.in_progress || [],
    score: row.score,
  };
}

async function getLeaderboard(days = 30) {
  const { data } = await API.get("/mission/leaderboard/", { params: { days } });
  return data;
}

async function pushCheckin(member, name, done, missed, date = today(), whatsappId = "", inProgress = [], pending = []) {
  const { data } = await API.post(
    "/mission/checkins/",
    {
      member, name, date, done, missed,
      in_progress: inProgress || [],
      pending: pending || [],
      whatsapp_id: whatsappId,
      source: "whatsapp",
    },
    { validateStatus: (s) => s < 500 }
  );
  if (data && data.detail) throw new Error(`push rejected: ${data.detail}`);
  return data;
}

/**
 * Make sure state belongs to today. HabitLog is the source of truth for
 * completion, so it seeds the owner's answers here; DailyCheckin is consulted
 * only for names/wids (HabitLog has no WhatsApp identity).
 */
async function ensureToday() {
  const t = today();
  if (state.date !== t) {
    state = { date: t, items: {}, chain: null, members: {}, dirty: [] };
    seededOn = "";
    chain = null;
    save();
  }
  if (seededOn !== t) {
    // names/wids from the check-in table
    try {
      const rows = await getCheckins(t);
      for (const r of rows) {
        const b = bucketFor(r.member, r.name, r.whatsapp_id);
        b.name = r.name || b.name || "";
        b.wid = r.whatsapp_id || b.wid || "";
      }
    } catch (e) {
      console.error("[mission] could not pull today's check-ins:", e.message);
    }
    // completion from HabitLog — same table the app reads
    try {
      const habits = await getHabits();
      const truth = await logAnswers(habits, t);
      const owner = (process.env.MISSION_OWNERS || "").split(",")[0].trim();
      if (owner) {
        const b = bucketFor(owner);
        b.done = truth.done;
        b.missed = truth.missed;
        b.in_progress = truth.in_progress || [];
        b.pending = truth.pending || [];
      }
      seededOn = t;
      save();
    } catch (e) {
      console.error("[mission] could not seed answers from HabitLog:", e.message);
    }
  }
  return state;
}

function bucketFor(id, name, wid) {
  if (!state.members[id]) {
    state.members[id] = {
      name: "", wid: "", done: [], missed: [], in_progress: [], pending: [],
    };
  }
  const b = state.members[id];
  if (!Array.isArray(b.in_progress)) b.in_progress = [];
  if (!Array.isArray(b.pending)) b.pending = [];
  if (name && !b.name) b.name = name;
  if (wid && !b.wid) b.wid = wid;
  return b;
}

/**
 * Answers for today, straight from the DB — the single source of truth.
 * Returns {done: [], missed: []} (empty when nothing is logged yet).
 *
 * The bot never reads its own local copy for display: if the answer isn't in
 * the DB, it isn't reported. setAnswer() buffers into `state` only so that a
 * failed push can be retried; once the push succeeds the DB owns the truth.
 */
async function dbAnswers(member, date = today()) {
  const row = await getMemberCheckin(member, date);
  return {
    done: (row && row.done) || [],
    missed: (row && row.missed) || [],
    in_progress: (row && row.in_progress) || [],
    row,
  };
}

/**
 * Set/clear one habit's answer for a member.
 * answer: "done" | "missed" | "in_progress" | "pending" | null
 *
 * A habit lives in exactly one bucket at a time: answering it again moves it
 * out of whatever bucket it was in.
 */
function setAnswer(id, name, wid, key, answer) {
  const b = bucketFor(id, name, wid);
  b.done = b.done.filter((k) => k !== key);
  b.missed = b.missed.filter((k) => k !== key);
  b.in_progress = (b.in_progress || []).filter((k) => k !== key);
  b.pending = (b.pending || []).filter((k) => k !== key);
  if (answer === "done") b.done.push(key);
  else if (answer === "missed") b.missed.push(key);
  else if (answer === "in_progress") b.in_progress.push(key);
  else if (answer === "pending") b.pending.push(key);
  if (!state.dirty.includes(id)) state.dirty.push(id);
  save();
  return b;
}

/**
 * Push one member to the backend and clear them from the dirty list.
 *
 * HabitLog is the source of truth, so before writing we take whatever is in it
 * and merge this member's pending local answer on top. Without this the bot's
 * in-memory buffer (possibly stale from earlier today) would overwrite edits
 * made in the app — e.g. reporting 10/10 after a single habit.
 */
async function syncMember(id) {
  const b = state.members[id];
  if (!b) return;
  let done = [...b.done];
  let missed = [...b.missed];
  let inProgress = [...(b.in_progress || [])];
  let pending = [...(b.pending || [])];
  try {
    const habits = await getHabits();
    const truth = await logAnswers(habits);
    // local answers win for the habits we changed this session; everything else
    // mirrors what the app currently has.
    const localDone = new Set(b.done);
    const localMissed = new Set(b.missed);
    const localInProgress = new Set(b.in_progress || []);
    const localPending = new Set(b.pending || []);
    const settled = new Set([
      ...localDone, ...localMissed, ...localInProgress, ...localPending,
    ]);
    for (const k of truth.done) if (!settled.has(k)) done.push(k);
    for (const k of truth.missed) if (!settled.has(k)) missed.push(k);
    for (const k of truth.in_progress) if (!settled.has(k)) inProgress.push(k);
    for (const k of truth.pending) if (!settled.has(k)) pending.push(k);
    done = [...new Set(done)];
    missed = [...new Set(missed)].filter((k) => !done.includes(k));
    inProgress = [...new Set(inProgress)].filter(
      (k) => !done.includes(k) && !missed.includes(k)
    );
    pending = [...new Set(pending)].filter(
      (k) => !done.includes(k) && !missed.includes(k) && !inProgress.includes(k)
    );
  } catch (e) {
    console.error(`[mission] couldn't read HabitLog before push (${id}):`, e.message);
  }
  await pushCheckin(id, b.name, done, missed, today(), b.wid, inProgress, pending);
  b.done = done;
  b.missed = missed;
  b.in_progress = inProgress;
  b.pending = pending;
  state.dirty = state.dirty.filter((x) => x !== id);
  save();
}

async function syncDirty() {
  for (const id of [...state.dirty]) {
    try {
      await syncMember(id);
    } catch (e) {
      console.error(`[mission] push failed for ${id}:`, e.message);
    }
  }
}

async function nameOf(client, wid) {
  try {
    const c = await client.getContactById(wid);
    return (c && (c.pushname || c.name || c.shortName)) || "";
  } catch (_) {
    return "";
  }
}

// ---------------------------------------------------------------- daily chain
/**
 * 20:00 — intro + one plain check-in message per habit, sent one by one.
 * The next habit goes out as soon as someone answers the current one;
 * one reminder after REMINDER_MS, move on after PROCEED_MS (see chain
 * machinery below).
 */
async function sendMorningCheckin(client) {
  if (!GROUP_ID) {
    console.warn("[mission] MISSION_GROUP_ID not set — skipping morning check-in");
    return;
  }
  if (!API_URL) {
    console.warn("[mission] MISSION_API_URL not set — skipping morning check-in");
    return;
  }
  try {
    await ensureToday();
    const habits = await getHabits();
    if (!habits.length) {
      console.warn("[mission] no active habits from the API — nothing to post");
      return;
    }
    clearTimers();
    chain = null;
    state.items = {};
    state.chain = null;
    save();

    const now = new Date();
    const day = now.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "short" });
    await client.sendMessage(
      GROUP_ID,
      `☀️ *Mission check-in — ${day}*\n` +
        `Going through today's ${habits.length} habits one by one.\n` +
        `Answer each with *done*, *in progress*, *pending* or *missed* — a reply ` +
        `to the message, or just type it.\n` +
        `Quiet for 5 minutes and I'll nudge you. Recap at ` +
        `${cronLabel(INTERIM_CRON, "10:00 PM")}, final tally at ${cronLabel(FINAL_CRON, "11:55 PM")}.`
    );

    chain = { client, habits };
    state.chain = { date: today(), index: 0, msgId: null, done: false };
    save();
    await sendChainItem(client, 0);
    console.log(`[mission] check-in chain started (${habits.length} habits, one by one)`);
  } catch (e) {
    console.error("[mission] morning check-in failed:", e.message);
  }
}

function clearTimers() {
  if (!chain) return;
  clearTimeout(chain.reminderTimer);
  clearTimeout(chain.proceedTimer);
  clearTimeout(chain.regTimer);
  chain.reminderTimer = null;
  chain.proceedTimer = null;
  chain.regTimer = null;
}

/** Reminder after REMINDER_MS of silence, move on after PROCEED_MS. */
function armTimers(client, h) {
  clearTimers();
  chain.reminderTimer = setTimeout(async () => {
    try {
      const text = `⏰ Reminder — *${h.name}* still not answered. Reply *done* / *missed*.`;
      try {
        await client.sendMessage(GROUP_ID, text, chain.msgId ? { quotedMessageId: chain.msgId } : {});
      } catch (_) {
        await client.sendMessage(GROUP_ID, text); // quoting can be rejected — never lose the nudge
      }
      console.log(`[mission] reminder sent for ${h.key}`);
    } catch (e) {
      console.error("[mission] reminder failed:", e.message);
    }
  }, REMINDER_MS);
  chain.proceedTimer = setTimeout(() => {
    advanceChain(client);
  }, PROCEED_MS);
}

/** Fallback id registration: read the chat's last messages back from the store. */
async function registerItemByFetch(client) {
  try {
    if (!chain || chain.msgId || !chain.pendingBody) return;
    const chat = await client.getChatById(GROUP_ID);
    const msgs = await chat.fetchMessages({ limit: 8 });
    for (const m of msgs || []) {
      if (m.fromMe && String(m.body || "").trim() === chain.pendingBody.trim() && m.id && m.id._serialized) {
        chain.msgId = m.id._serialized;
        state.items[m.id._serialized] = chain.key;
        if (state.chain) state.chain.msgId = m.id._serialized;
        save();
        console.log(`[mission] item ${chain.key} registered via fetch (${m.id._serialized})`);
        return;
      }
    }
    console.log("[mission] fetch-register: pending item not found among last messages");
  } catch (e) {
    console.error("[mission] fetch-register failed:", e.message);
  }
}

/** Send the check-in message for habits[index] and start waiting for an answer. */
async function sendChainItem(client, index) {
  const habits = (chain && chain.habits) || [];
  const h = habits[index];
  if (!h) {
    await finishChain(client);
    return;
  }
  const text = `*${h.name}* ${h.emoji}\nReply *done*, *in progress*, *pending* or *missed* — or just type it.`;
  // pendingBody must be set BEFORE sending: our own message_create can
  // arrive while the send promise is still resolving.
  Object.assign(chain, { index, key: h.key, name: h.name, msgId: null, settled: false, pendingBody: text });

  let sent = null;
  try {
    sent = await client.sendMessage(GROUP_ID, text);
  } catch (e) {
    console.error(`[mission] could not send check-in for ${h.key}:`, e.message);
  }
  const msgId = sent && sent.id && sent.id._serialized ? sent.id._serialized : null;
  if (msgId) {
    chain.msgId = msgId;
    state.items[msgId] = h.key;
    save();
  }

  state.chain = { date: today(), index, msgId: chain.msgId, done: false };
  save();
  armTimers(client, h);
  // if neither the return path nor message_create gave us the id, read it back
  if (!chain.msgId) {
    chain.regTimer = setTimeout(() => registerItemByFetch(client), 1500);
  }
}

/** Settle the current item (answered or timed out) and send the next one. */
async function advanceChain(client) {
  if (!chain || chain.settled) return;
  chain.settled = true;
  clearTimers();
  const next = chain.index + 1;
  state.chain = { date: today(), index: next, msgId: null, done: false };
  save();
  await delay(1000);
  await sendChainItem(client, next);
}

async function finishChain(client) {
  clearTimers();
  const count = (chain && chain.habits) ? chain.habits.length : 0;
  state.chain = state.chain || { date: today(), index: count, msgId: null };
  state.chain.done = true;
  save();
  try {
    await client.sendMessage(GROUP_ID, `✅ That's all ${count} habits for today — late replies still count.`);
  } catch (_) {}
  console.log("[mission] check-in chain finished for today");
  chain = null;
}

/**
 * "done" / "yes" / "✅" / "haan" → "done"; "missed" / "no" / "❌" / "nahi" → "missed";
 * "in progress" / "started" / "doing" → "in_progress"; "pending" / "not yet" → "pending".
 */
function answerFrom(text) {
  const t = String(text || "").trim().toLowerCase().replace(/[.!?،\s]+$/u, "");
  if (/^(done|yes|y|haan|ha|done✅|✅|✔️|👍)$/.test(t)) return "done";
  if (/^(missed|miss|no|n|nahi|nah|missed❌|❌|👎)$/.test(t)) return "missed";
  // "in progress" / "inprogress" / "started" / "doing" / "wip"
  if (/^(in[ _-]?progress|inprogress|started|doing|wip|🔄|🚧)$/.test(t)) return "in_progress";
  // "pending" / "not yet" / "later" — nothing started
  if (/^(pending|not[ _-]?yet|not[ _-]?started|later|⏳)$/.test(t)) return "pending";
  return null;
}

/** Human icon for an answer status. */
function answerIcon(answer) {
  if (answer === "done") return "✅ done";
  if (answer === "missed") return "❌ missed";
  if (answer === "in_progress") return "🔄 in progress";
  if (answer === "pending") return "⏳ pending";
  return answer;
}

/** Record one answer for a member and push it to the backend. */
async function recordAnswer(client, wid, key, answer) {
  const id = normalizeId(wid);
  const name = await nameOf(client, wid);
  const b = setAnswer(id, name, widen(wid), key, answer);
  try {
    await syncMember(id);
  } catch (e) {
    console.error(`[mission] push failed for ${id}:`, e.message); // stays dirty, retried at recap
  }
  return b;
}

/**
 * Someone answered the currently pending check-in (first answer wins the
 * advance; others can still reply-quote older items any time today).
 */
async function answerPending(client, wid, key, answer) {
  if (!chain || chain.settled || chain.key !== key) return false;
  const name = await nameOf(client, wid);
  setAnswer(normalizeId(wid), name, widen(wid), key, answer);
  let doneCount = null;
  let pushErr = null;
  try {
    await syncMember(normalizeId(wid));
    // count from HabitLog — the same table the app shows
    const fresh = await logAnswers(chain.habits);
    doneCount = fresh.done.length;
  } catch (e) {
    pushErr = e.message;
    console.error(`[mission] push failed:`, e.message);
  }
  try {
    const icon = answerIcon(answer);
    const who = name ? ` (${name})` : "";
    if (pushErr) {
      await client.sendMessage(
        GROUP_ID,
        `⚠️ *${chain.name}* → ${answer} — but something went wrong saving it ` +
          `(${cut(pushErr, 120)}). It's queued and will sync when the server is back.`
      );
    } else {
      await client.sendMessage(
        GROUP_ID,
        `✔️ *${chain.name}* → ${icon}${who} · ${doneCount}/${chain.habits.length}`
      );
    }
  } catch (_) {}
  console.log(`[mission] ${key} answered (${answer}) — next habit`);
  await advanceChain(client);
  return true;
}

/**
 * Group message → mission check-in. Three ways to answer:
 *   1. reply-quote one of today's check-in messages with done/missed
 *   2. type done/missed while an item is pending
 *   3. !mission done <habit> (handled in handleCommand — also advances)
 */
async function onMessage(client, msg) {
  try {
    if (!GROUP_ID || !msg) return;
    if (msg.from !== GROUP_ID || msg.fromMe) return; // our own sends go to onOwnMessage
    const wid = msg.author || msg.from;
    const sender = normalizeId(wid);
    if (!sender) return;
    const body = String(msg.body || "").trim();
    if (!body || body.startsWith("!")) return;
    const answer = answerFrom(body);
    if (!answer) return;

    // 1) a quoted reply pins the answer to a specific habit
    if (msg.hasQuotedMsg) {
      try {
        const q = await msg.getQuotedMessage();
        const key = q && q.id && q.id._serialized ? state.items[q.id._serialized] : null;
        if (key) {
          if (chain && !chain.settled && chain.key === key) {
            await answerPending(client, wid, key, answer);
          } else {
            const b = await recordAnswer(client, wid, key, answer);
            console.log(`[mission] late ${answer} for ${key} from ${sender} (${b.done.length} done today)`);
          }
          return;
        }
      } catch (_) {
        /* quoted lookup unavailable — fall through to the bare word */
      }
    }

    // 2) bare word while an item is pending → that item
    if (chain && !chain.settled) {
      await answerPending(client, wid, chain.key, answer);
    }
  } catch (e) {
    console.error("[mission] message handling failed:", e.message);
  }
}

/**
 * Our own outgoing message → register its id for the pending item.
 * (client.sendMessage's return path can come back empty on this WA build,
 * so message_create is the reliable way to learn the message id.)
 */
function onOwnMessage(msg) {
  try {
    if (!chain || !chain.pendingBody || !msg || !msg.fromMe) return false;
    // compare on the numeric part: this build can address the group by its
    // lid suffix instead of "@g.us" on outgoing messages
    const chatId = msg.chat || msg.to || msg.from;
    if (GROUP_ID && normalizeId(chatId) !== normalizeId(GROUP_ID)) return false;
    if (String(msg.body || "").trim() !== chain.pendingBody.trim()) return false;
    const id = msg.id && msg.id._serialized;
    if (!id) return false;
    if (!state.items[id]) {
      state.items[id] = chain.key;
      save();
    }
    if (!chain.msgId) {
      chain.msgId = id;
      state.chain = { date: today(), index: chain.index, msgId: id, done: false };
      save();
      console.log(`[mission] item ${chain.key} registered via message_create (${id})`);
    }
    return true;
  } catch (_) {
    return false;
  }
}

/** Bot restart mid-chain (crash, deploy) → pick the day's chain back up. */
async function resumeChain(client) {
  if (!GROUP_ID || !API_URL) return;
  const c = state.chain;
  if (!c || c.date !== today() || c.done) return;
  try {
    await ensureToday();
    const habits = await getHabits();
    if (!habits.length) return;
    chain = { client, habits };
    const idx = Math.min(c.index || 0, habits.length);
    const h = habits[idx];
    if (!h) {
      state.chain.done = true;
      save();
      chain = null;
      return;
    }
    if (c.msgId) {
      // the item is already sitting in the group — just wait on it again
      Object.assign(chain, { index: idx, key: h.key, name: h.name, msgId: c.msgId, settled: false, pendingBody: null });
      armTimers(client, h);
      console.log(`[mission] chain resumed at ${h.key} (item already sent)`);
    } else {
      await sendChainItem(client, idx);
      console.log(`[mission] chain resumed — sent ${h.key}`);
    }
  } catch (e) {
    console.error("[mission] chain resume failed:", e.message);
  }
}

// ---------------------------------------------------------------- votes
/** Legacy poll-vote hook — polls were replaced by plain messages (see above). */
async function onVote() {
  /* no-op: nothing sends mission polls anymore */
}

// ---------------------------------------------------------------- recaps
/**
 * Rows for the recap. One line per member that has a DB row — the DB is the
 * source of truth, so nothing is shown that isn't actually recorded.
 */
function renderRows(habits, rows) {
  const total = habits.length || 1;
  const lines = [];

  const merged = rows.map((r) => ({
    id: r.member,
    name: r.name || r.member,
    done: (r.done || []).length,
    inProgress: (r.in_progress || []).length,
    wid: r.whatsapp_id || "",
    reported: true,
  }));

  merged.sort((a, b) => b.done - a.done || String(a.name).localeCompare(String(b.name)));
  for (const m of merged) {
    const who = m.name && m.name !== m.id ? m.name : `@${m.id}`;
    const icon = m.done >= total ? "✅" : m.done > 0 ? "🟡" : "🔴";
    // in-progress is shown but never counted as done
    const extra = m.inProgress ? `  (+${m.inProgress}🔄)` : "";
    lines.push(`${icon} ${who}  ${bar(m.done, total)}  ${m.done}/${total}${extra}`);
  }
  return lines;
}

/** Who in the group hasn't reported yet (best effort — never fails the recap). */
async function pendingMentions(client, reportedIds) {
  if (!GROUP_ID) return [];
  try {
    const chat = await client.getChatById(GROUP_ID);
    const me = client.info && client.info.wid ? normalizeId(client.info.wid._serialized) : "";
    const out = [];
    for (const p of chat.participants || []) {
      const raw = typeof p.id === "object" ? p.id._serialized : p.id;
      const id = normalizeId(raw);
      if (!id || id === me || reportedIds.has(id)) continue;
      const known = state.members[id];
      const name = (known && known.name) || (await nameOf(client, raw));
      out.push({ id, wid: raw, name: name || id });
    }
    return out.slice(0, 15);
  } catch (_) {
    return [];
  }
}

/**
 * 22:00 interim / 23:55 final recap.
 * Pushes anything the API missed first, then posts a per-person progress bar
 * (+ 30-day streak leaderboard on the final one).
 */
async function sendRecap(client, opts = {}) {
  const final = !!(opts && opts.final);
  if (!GROUP_ID) return;
  try {
    await ensureToday();
    await syncDirty();

    const [habits, rows] = await Promise.all([getHabits(), getCheckins()]);
    const reported = new Set(rows.map((r) => r.member));

    const now = new Date();
    const time = now.toLocaleTimeString("en-IN", { hour: "numeric", minute: "2-digit", hour12: true });
    const title = final ? "🏁 *Mission — final recap*" : "🌙 *Mission — interim recap*";
    const rowsText = renderRows(habits, rows);
    let text = `${title} (${time})\n${habits.length} habits · ${rows.length} reporting\n\n` +
      rowsText.join("\n");

    const mentions = [];
    // wids come from the DB rows now (CheckinMember.whatsapp_id)
    for (const r of rows) {
      if (r.whatsapp_id) mentions.push({ id: r.member, wid: r.whatsapp_id });
    }
    const pending = await pendingMentions(client, reported);
    if (pending.length) {
      text += `\n\n⏳ *Not checked in yet:* ${pending
        .map((p) => (p.name && p.name !== p.id ? p.name : "@" + p.id))
        .join(", ")}`;
      for (const p of pending) mentions.push(p);
    }

    if (final) {
      try {
        const lb = await getLeaderboard(30);
        const top = (lb.members || []).filter((m) => m.streak > 0).slice(0, 3);
        if (top.length) {
          text +=
            "\n\n🏆 *30-day streaks:* " +
            top.map((m) => `${m.name || m.member} — ${m.streak}d (${m.avg_score}%)`).join(" · ");
        }
      } catch (e) {
        console.error("[mission] leaderboard fetch failed:", e.message);
      }
    } else {
      text += `\n\n🚨 Final recap at ${cronLabel(FINAL_CRON, "11:55 PM")} — last call to vote!`;
    }

    const widMentions = mentions.map((m) => m.wid).filter((w) => /@(c\.us|lid)$/.test(w));
    try {
      await client.sendMessage(GROUP_ID, text, widMentions.length ? { mentions: widMentions } : {});
    } catch (_) {
      await client.sendMessage(GROUP_ID, text); // mentions can be rejected — never lose the recap
    }
    console.log(`[mission] ${final ? "final" : "interim"} recap sent (${rowsText.length} rows)`);
  } catch (e) {
    console.error("[mission] recap failed:", e.message);
  }
}

// ---------------------------------------------------------------- commands
function resolveHabit(habits, query) {
  const q = String(query || "").trim().toLowerCase();
  if (!q) return null;
  const key = slug(q);
  return (
    habits.find((h) => h.key === key) ||
    habits.find((h) => h.name.toLowerCase() === q) ||
    (q.length >= 3 ? habits.find((h) => h.name.toLowerCase().includes(q)) : null)
  );
}

function progressLine(done, total) {
  return `${bar(done, total)}  ${done}/${total}`;
}

async function reply(msg, text) {
  try {
    await msg.reply(text, null, {});
  } catch (e) {
    console.error("[mission] reply failed:", e.message);
  }
}

/** Short one-line truncation for error text. */
function cut(s, n = 200) {
  const t = String(s == null ? "" : s).replace(/\s+/g, " ").trim();
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

/** !mission / !mission done <habit> / !mission missed <habit> / !mission habits */
async function handleCommand(client, msg) {
  try {
    const parts = String(msg.body || "").trim().split(/\s+/);
    const sub = (parts[1] || "").toLowerCase();
    const arg = parts.slice(2).join(" ");

    if (!API_URL) {
      await reply(msg, "Mission server isn't configured (MISSION_API_URL missing).");
      return;
    }

    await ensureToday();
    const sender = normalizeId(msg.author || msg.from);
    const habits = await getHabits();

    if (!sub || sub === "status") {
      // Read HabitLog — the SAME table the Flutter app reads. That makes the
      // bot and the app incapable of disagreeing, whatever either one writes.
      let b;
      try {
        b = await logAnswers(habits);
      } catch (e) {
        await reply(msg, `⚠️ Couldn't reach the server: ${cut(e.message, 200)}`);
        return;
      }
      const doneCount = b.done.length;
      const missedCount = b.missed.length;
      const inProgressCount = (b.in_progress || []).length;
      const pending = habits.filter(
        (h) =>
          !b.done.includes(h.key) &&
          !b.missed.includes(h.key) &&
          !(b.in_progress || []).includes(h.key)
      );
      let text = `📋 *Your check-in — ${new Date().toLocaleDateString("en-IN", {
        weekday: "short",
        day: "numeric",
        month: "short",
      })}*\n`;
      if (!doneCount && !missedCount && !inProgressCount) {
        text += "Nothing logged yet today — answer today's check-in messages, or tap in the app.\n";
      } else {
        for (const h of habits) {
          if (b.done.includes(h.key)) text += `✅ ${h.name}\n`;
          else if (b.missed.includes(h.key)) text += `❌ ${h.name}\n`;
          else if ((b.in_progress || []).includes(h.key)) text += `🔄 ${h.name} (in progress)\n`;
        }
      }
      text += `\n${progressLine(doneCount, habits.length || 1)}`;
      if (inProgressCount) {
        text += `\n🔄 In progress: ${inProgressCount}`;
      }
      if (pending.length) {
        text += `\n⏳ Still pending: ${pending.slice(0, 6).map((h) => h.name).join(", ")}` +
          (pending.length > 6 ? ` +${pending.length - 6} more` : "");
      }
      await reply(msg, text);
      return;
    }

    if (sub === "habits") {
      let text = `*Today's habits* (${habits.length}):\n`;
      for (const h of habits) text += `${h.emoji} ${h.name}  →  ${h.key}\n`;
      text +=
        "\nMark one with `!mission done <habit>` — also `in_progress`, `pending` " +
        "or `missed`.";
      await reply(msg, text);
      return;
    }

    if (sub === "done" || sub === "missed" || sub === "in_progress" || sub === "pending") {
      const habit = resolveHabit(habits, arg);
      if (!habit) {
        await reply(
          msg,
          arg
            ? `No habit matches "*${arg}*". Try \`!mission habits\` for the list.`
            : `Usage: !mission ${sub} <habit> — e.g. \`!mission ${sub} ${habits[0] ? habits[0].name : "5L Water"}\``
        );
        return;
      }
      const wid = msg.author || msg.from;
      const name = await nameOf(client, wid);
      setAnswer(sender, name, widen(wid), habit.key, sub);
      let pushed = true;
      try {
        await syncMember(sender);
      } catch (e) {
        pushed = false;
        console.error("[mission] push failed:", e.message);
      }
      const icon =
        sub === "done" ? "✅" : sub === "missed" ? "❌" : sub === "in_progress" ? "🔄" : "⏳";
      // report the count as HabitLog has it — the app's own number
      if (!pushed) {
        await reply(
          msg,
          `⚠️ Something went wrong saving *${habit.name}* to the server — it's ` +
            `queued locally and will sync automatically when the server is back.`
        );
        return;
      }
      const fresh = await logAnswers(habits);
      const line = progressLine(fresh.done.length, habits.length || 1);
      await reply(msg, `${icon} Logged *${habit.name}* — ${line} today.`);
      // answering today's pending check-in this way also advances the chain
      if (msg.from === GROUP_ID && chain && !chain.settled && chain.key === habit.key) {
        await advanceChain(client);
      }
      return;
    }

    await reply(
      msg,
      "*Mission commands*\n" +
        "`!mission` — today's status\n" +
        "`!mission done <habit>` — mark a habit done\n" +
        "`!mission missed <habit>` — mark a habit missed\n" +
        "`!mission habits` — list today's habits"
    );
  } catch (e) {
    console.error("[mission] command failed:", e.message);
    // Be honest: it may be the server, but it may be a bug — don't guess.
    await reply(msg, `⚠️ Something went wrong running that command: ${cut(e.message, 200)}`);
  }
}

module.exports = {
  sendMorningCheckin,
  sendRecap,
  onVote,
  onMessage,
  onOwnMessage,
  resumeChain,
  handleCommand,
  // building blocks (also used by tests)
  getHabits,
  getCheckins,
  getHabitLogs,
  logAnswers,
  getMemberCheckin,
  dbAnswers,
  getLeaderboard,
  pushCheckin,
  ensureToday,
  setAnswer,
  slug,
  bar,
  cronLabel,
  normalizeId,
  resolveHabit,
  answerFrom,
  today,
  MORNING_CRON,
  INTERIM_CRON,
  FINAL_CRON,
  REMINDER_MS,
  PROCEED_MS,
  GROUP_ID,
  API_URL,
  getState: () => state,
  getChain: () => chain,
  reset() {
    state = { date: "", items: {}, chain: null, members: {}, dirty: [] };
    seededOn = "";
    chain = null;
    try {
      fs.unlinkSync(STATE_FILE);
    } catch (_) {}
  },
};
