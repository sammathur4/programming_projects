'use strict';
/* ============================================================
   Momentum — Habit & Goal Tracker (HabitBull + Legend style)
   Data lives in localStorage. Export/Import for backup.
   ============================================================ */

/* ---------------- tiny helpers ---------------- */
const $  = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => Array.from(el.querySelectorAll(s));
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
const uid = () => Math.random().toString(36).slice(2, 9) + Date.now().toString(36).slice(-3);
const pad = n => String(n).padStart(2, '0');
const fmtDate = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const parseDate = s => { const [y, m, d] = s.split('-').map(Number); return new Date(y, m - 1, d); };
const addDays = (d, n) => { const x = new Date(d); x.setDate(x.getDate() + n); return x; };
const todayStr = () => fmtDate(new Date());
const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
const num = v => { const n = parseFloat(v); return isFinite(n) ? n : 0; };
const inr = n => '₹' + Number(n).toLocaleString('en-IN');

const DAYS_SHORT = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];
const DAY_NAMES  = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const COLORS = ['#22c55e', '#3b82f6', '#a855f7', '#f59e0b', '#ef4444', '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#eab308', '#14b8a6', '#6366f1'];
const EMOJIS = ['⏰', '🧘', '📚', '🏋️', '🚶', '💧', '😴', '🎸', '💻', '🚫', '📖', '🧴', '🧠', '✍️', '🥗', '⏱️', '🙏', '☀️', '🎯', '🧹', '💸', '🏃', '🧊', '📵'];
const CATEGORIES = ['Health', 'Fitness', 'Mind', 'Study', 'Discipline', 'Skills', 'Self-care'];
const EXERCISE_CATALOG = [
  'Bench Press', 'Incline DB Press', 'Overhead Press', 'Dips', 'Cable Fly',
  'Barbell Row', 'Pull Up', 'Lat Pulldown', 'Face Pull', 'Barbell Curl', 'Hammer Curl',
  'Squat', 'Deadlift', 'Romanian Deadlift', 'Leg Press', 'Lunge', 'Calf Raise', 'Leg Extension',
  'Lateral Raise', 'Tricep Pushdown', 'Plank', 'Crunch'
];

/* ---------------- state ---------------- */
const STORAGE_KEY = 'momentum_habits_v1';

function seedState() {
  const t = todayStr();
  const mk = (emoji, name, category, type, opts = {}) => Object.assign({
    id: uid(), emoji, name, category, type,
    color: COLORS[0], target: 1, unit: '',
    freq: { type: 'daily', days: [] },
    createdAt: t
  }, opts);

  const habits = [
    mk('⏰', 'Wake up 5 AM', 'Discipline', 'check',   { color: '#f59e0b' }),
    mk('🧘', 'Meditation', 'Mind', 'count',           { color: '#a855f7', target: 20, unit: 'min' }),
    mk('📚', 'UPSC Study', 'Study', 'count',          { color: '#3b82f6', target: 6, unit: 'hrs' }),
    mk('✍️', 'Answer Writing', 'Study', 'check',       { color: '#06b6d4', freq: { type: 'days', days: [1, 3, 5] } }),
    mk('🏋️', 'Gym Workout', 'Fitness', 'workout',      { color: '#22c55e', freq: { type: 'days', days: [1, 2, 3, 4, 5, 6] } }),
    mk('🚶', 'Steps', 'Health', 'count',              { color: '#84cc16', target: 10000, unit: 'steps' }),
    mk('💧', 'Water', 'Health', 'count',              { color: '#06b6d4', target: 8, unit: 'glasses' }),
    mk('😴', 'Sleep by 10 PM', 'Self-care', 'check',   { color: '#6366f1' }),
    mk('🎸', 'Guitar Practice', 'Skills', 'count',     { color: '#ec4899', target: 30, unit: 'min' }),
    mk('💻', 'Code Practice', 'Skills', 'check',       { color: '#14b8a6', freq: { type: 'days', days: [0, 2, 4, 6] } }),
    mk('🚫', 'NoFap', 'Discipline', 'check',           { color: '#ef4444' }),
    mk('🥗', 'No Sugar / Junk', 'Health', 'check',     { color: '#eab308' })
  ];

  const goals = [
    { id: uid(), emoji: '🎯', title: 'UPSC 2027 — AIR 1', unit: 'syllabus %', target: 100, current: 0, deadline: '2027-05-24', linkExercise: '' },
    { id: uid(), emoji: '🏋️', title: 'Bench Press 100 kg', unit: 'kg', target: 100, current: 0, deadline: '', linkExercise: 'Bench Press' },
    { id: uid(), emoji: '💸', title: 'Savings ₹50,00,000', unit: '₹', target: 5000000, current: 0, deadline: '2027-12-31', linkExercise: '' },
    { id: uid(), emoji: '🎸', title: 'Learn 50 songs', unit: 'songs', target: 50, current: 0, deadline: '', linkExercise: '' }
  ];

  return { habits, goals, logs: {}, notes: {}, workouts: [], createdAt: t };
}

let state;
let stateLoaded = false;
try {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (raw) { const p = JSON.parse(raw); if (p && Array.isArray(p.habits)) { state = p; stateLoaded = true; } }
} catch (e) { console.warn('Load failed', e); }
if (!state) state = seedState();
state.goals = state.goals || [];
state.workouts = state.workouts || [];
state.logs = state.logs || {};
state.notes = state.notes || {};

function save() { try { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); } catch (e) { console.warn('Save failed', e); } }

/* ---------------- UI state ---------------- */
const ui = {
  tab: 'today',
  date: todayStr(),        // selected date on Today view
  gridDays: 30,
  chartEx: null,
  filter: 'all'
};

/* ---------------- core habit logic ---------------- */
function isDue(h, ds) {
  if (h.createdAt && ds < h.createdAt.slice(0, 10)) return false;
  if (!h.freq || h.freq.type === 'daily') return true;
  const want = h.freq.days || [];
  return want.includes(parseDate(ds).getDay());
}
function logKey(hid, ds) { return hid + '|' + ds; }
function getLog(hid, ds) { return state.logs[logKey(hid, ds)] || { count: 0 }; }
function sessionFor(ds) { return state.workouts.find(w => w.date === ds) || null; }

function isDone(h, ds) {
  if (h.type === 'workout') return !!sessionFor(ds);
  const c = num(getLog(h.id, ds).count);
  return c >= (h.target || 1);
}
function setCount(h, ds, count) {
  const k = logKey(h.id, ds);
  const v = Math.max(0, count);
  if (v <= 0) delete state.logs[k];
  else state.logs[k] = { count: v, done: v >= (h.target || 1) };
  save();
}
function toggleHabit(h, ds) {
  if (h.type === 'workout') { openWorkoutSheet(null, ds); return; }
  setCount(h, ds, isDone(h, ds) ? 0 : (h.target || 1));
}
function adjustCount(h, ds, delta) {
  const c = num(getLog(h.id, ds).count) + delta;
  setCount(h, ds, c);
}

function currentStreak(h) {
  let d = new Date(), s = 0;
  for (let i = 0; i < 1500; i++) {
    const ds = fmtDate(d);
    if (h.createdAt && ds < h.createdAt.slice(0, 10)) break;
    if (isDue(h, ds)) {
      if (isDone(h, ds)) s++;
      else if (i > 0) break;      // yesterday (or older) missed → streak over; today pending = grace
    }
    d = addDays(d, -1);
  }
  return s;
}
function bestStreak(h) {
  const startStr = (h.createdAt || fmtDate(addDays(new Date(), -365))).slice(0, 10);
  let start = parseDate(startStr);
  const end = new Date();
  let s = 0, best = 0, guard = 0;
  for (let d = start; d <= end && guard < 1500; d = addDays(d, 1), guard++) {
    const ds = fmtDate(d);
    if (isDue(h, ds)) {
      if (isDone(h, ds)) { s++; if (s > best) best = s; }
      else s = 0;
    }
  }
  return best;
}
function completion(h, days) {
  let due = 0, done = 0;
  const today = new Date();
  for (let i = 0; i < days; i++) {
    const ds = fmtDate(addDays(today, -i));
    if (isDue(h, ds)) { due++; if (isDone(h, ds)) done++; }
  }
  return due ? Math.round((done / due) * 100) : null;
}
function dayStats(ds) {
  const due = state.habits.filter(h => isDue(h, ds));
  const done = due.filter(h => isDone(h, ds)).length;
  return { due: due.length, done, pct: due.length ? Math.round((done / due.length) * 100) : null };
}
function activeHabits() { return state.habits.filter(h => ui.filter === 'all' || h.category === ui.filter); }
function habitById(id) { return state.habits.find(h => h.id === id); }

/* ---------------- workout helpers ---------------- */
function workoutVolume(w) {
  let v = 0;
  (w.exercises || []).forEach(e => (e.sets || []).forEach(s => { v += num(s.weight) * num(s.reps); }));
  return Math.round(v);
}
function prFor(exName, exceptWorkoutId) {
  let best = null;
  state.workouts.forEach(w => {
    if (w.id === exceptWorkoutId) return;
    const e = (w.exercises || []).find(x => x.name === exName);
    if (!e) return;
    e.sets.forEach(s => {
      const wt = num(s.weight);
      if (wt > 0 && (!best || wt > best.weight)) best = { weight: wt, reps: num(s.reps), date: w.date };
    });
  });
  return best;
}
function exerciseHistory(exName) {
  return state.workouts
    .map(w => {
      const e = (w.exercises || []).find(x => x.name === exName);
      if (!e) return null;
      const top = e.sets.reduce((m, s) => Math.max(m, num(s.weight)), 0);
      return top > 0 ? { date: w.date, weight: top } : null;
    })
    .filter(Boolean)
    .sort((a, b) => a.date.localeCompare(b.date));
}
function usedExercises() {
  const set = new Set();
  state.workouts.forEach(w => (w.exercises || []).forEach(e => set.add(e.name)));
  return Array.from(set);
}

/* ---------------- toast ---------------- */
let toastTimer = null;
function toast(msg) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
}

/* ---------------- formatting ---------------- */
function prettyDate(ds) {
  const d = parseDate(ds), now = new Date();
  const yest = fmtDate(addDays(now, -1)), tom = fmtDate(addDays(now, 1));
  let label = DAY_NAMES[d.getDay()] + ', ' + d.getDate() + ' ' + MONTHS[d.getMonth()];
  if (ds === todayStr()) label = 'Today, ' + d.getDate() + ' ' + MONTHS[d.getMonth()];
  else if (ds === yest) label = 'Yesterday, ' + d.getDate() + ' ' + MONTHS[d.getMonth()];
  else if (ds === tom) label = 'Tomorrow, ' + d.getDate() + ' ' + MONTHS[d.getMonth()];
  return { main: label, sub: d.getFullYear() !== now.getFullYear() ? String(d.getFullYear()) : (ds === todayStr() ? DAY_NAMES[d.getDay()] : '') };
}
function fmtMetric(h, c) {
  const u = h.unit || '';
  if (u === 'steps' || u === '₹') return Number(c).toLocaleString('en-IN') + (u === 'steps' ? '' : '');
  return c + (u ? ' ' + u : '');
}

/* ============================================================
   RENDER — TODAY
   ============================================================ */
function renderToday() {
  const ds = ui.date;
  const st = dayStats(ds);
  const pd = prettyDate(ds);
  const isToday = ds === todayStr();
  const habits = activeHabits();
  const note = state.notes[ds] || '';

  const ringPct = st.pct ?? 0;
  const ringColor = ringPct === 100 ? '#22c55e' : ringPct >= 50 ? '#3b82f6' : '#f59e0b';
  const doneHabits = st.due ? st.done : 0;
  const remaining = (st.due || 0) - (st.done || 0);

  const cards = habits.map(h => {
    const due = isDue(h, ds);
    const done = isDone(h, ds);
    const streak = currentStreak(h);
    const count = num(getLog(h.id, ds).count);
    const pctTarget = h.type === 'count' && h.target ? clamp(Math.round((count / h.target) * 100), 0, 100) : 0;
    const sess = h.type === 'workout' ? sessionFor(ds) : null;

    let right = '';
    if (h.type === 'check') {
      right = `<button class="check-btn ${done ? 'on' : ''}" data-action="toggle-habit" data-id="${h.id}" data-date="${ds}" ${due ? '' : 'disabled'} aria-label="toggle">${done ? '✓' : ''}</button>`;
    } else if (h.type === 'count') {
      right = `
        <div class="counter">
          <button class="icon-btn" data-action="count-dec" data-id="${h.id}" data-date="${ds}" ${due ? '' : 'disabled'}>−</button>
          <div class="val">${fmtMetric(h, count)}<small>of ${fmtMetric(h, h.target)}</small></div>
          <button class="icon-btn" data-action="count-inc" data-id="${h.id}" data-date="${ds}" ${due ? '' : 'disabled'}>+</button>
        </div>`;
    } else {
      right = `<button class="btn ${sess ? 'primary' : 'blue'} small" data-action="open-workout" data-date="${ds}">${sess ? '✓ Logged · Edit' : '＋ Log'}</button>`;
    }

    const metaBits = [];
    if (!due) metaBits.push('<span class="tag">rest day</span>');
    if (streak > 0) metaBits.push(`<span class="streak">🔥 ${streak}</span>`);
    if (h.type === 'count') metaBits.push(`${fmtMetric(h, count)} / ${fmtMetric(h, h.target)}`);
    if (h.type === 'workout' && sess) metaBits.push(`${(sess.exercises || []).length} exercises · ${workoutVolume(sess).toLocaleString('en-IN')} kg vol`);
    if (h.type === 'check') metaBits.push(done ? 'completed' : (due ? 'pending' : '—'));

    const bar = h.type === 'count'
      ? `<div class="mini-progress"><i style="width:${pctTarget}%"></i></div>` : '';

    return `
      <div class="habit-card ${done ? 'done' : ''} ${due ? '' : 'rest'}" style="--hc:${h.color}">
        <div class="habit-emoji">${h.emoji}</div>
        <div class="habit-main">
          <div class="habit-name">${esc(h.name)} <span class="tag">${esc(h.category)}</span></div>
          <div class="habit-meta">${metaBits.join('')}</div>
          ${bar}
        </div>
        ${right}
      </div>`;
  }).join('');

  $('#view-today').innerHTML = `
    <div class="today-top">
      <div class="today-nav">
        <button class="icon-btn" data-action="date-prev" aria-label="previous day">‹</button>
        <button class="icon-btn" data-action="date-next" aria-label="next day" ${isToday ? 'disabled' : ''}>›</button>
      </div>
      <div class="today-date">
        <div class="d1">${pd.main}</div>
        <div class="d2">${pd.sub || 'Log your habits'}</div>
        ${isToday ? '<span class="pill today">● today</span>' : `<button class="pill" data-action="date-today" style="border:none;cursor:pointer;font-family:inherit">back to today</button>`}
      </div>
      <div class="ring" style="--pct:${ringPct}; --ring:${ringColor}"><span>${st.pct === null ? '—' : ringPct + '%'}</span></div>
    </div>

    <div class="today-summary">
      ${st.due
        ? `<b>${doneHabits}/${st.due}</b> habits done${remaining > 0 ? ` · <b>${remaining}</b> to go` : ' · 🎉 perfect day!'}`
        : 'No habits scheduled today — enjoy the rest day.'}
    </div>

    ${habits.length ? cards : `<div class="empty"><b>No habits yet.</b><br>Open the ▦ Habits tab to create your first habit.</div>`}

    <div class="card note-box" style="margin-top:12px">
      <div class="note-label">📝 Note for ${pd.main.split(',')[0]}</div>
      <textarea id="dayNote" placeholder="How did today go? Wins, blockers, ideas…">${esc(note)}</textarea>
    </div>`;

  const ta = $('#dayNote');
  if (ta) ta.addEventListener('input', () => { state.notes[ds] = ta.value; save(); });
}

/* ============================================================
   RENDER — HABITS GRID (HabitBull style)
   ============================================================ */
function renderHabits() {
  const days = ui.gridDays;
  const today = new Date();
  const dates = [];
  for (let i = days - 1; i >= 0; i--) dates.push(fmtDate(addDays(today, -i)));
  const habits = activeHabits();
  const cats = ['all', ...Array.from(new Set(state.habits.map(h => h.category)))];

  const headCells = dates.map(ds => {
    const d = parseDate(ds);
    const wknd = d.getDay() === 0 || d.getDay() === 6;
    const now = ds === todayStr();
    return `<th class="${wknd ? 'wknd' : ''} ${now ? 'now' : ''}"><span class="dl">${DAYS_SHORT[d.getDay()]}</span>${d.getDate()}</th>`;
  }).join('');

  const rows = habits.map(h => {
    const streak = currentStreak(h);
    const cells = dates.map(ds => {
      const due = isDue(h, ds);
      const future = ds > todayStr();
      const made = !h.createdAt || ds >= h.createdAt.slice(0, 10);
      let cls = 'cell', title = `${h.name} — ${ds}`;
      if (future || !made) { cls += ' future'; return `<td><span class="${cls}" title="${esc(title)}"></span></td>`; }
      if (!due) { cls += ' rest'; return `<td><span class="${cls}" title="${esc(title)} — rest day"></span></td>`; }
      const done = isDone(h, ds);
      const count = num(getLog(h.id, ds).count);
      if (done) { cls += ' done'; title += ' ✓ done'; }
      else if (count > 0) { cls += ' part'; title += ` partial (${fmtMetric(h, count)})`; }
      else title += ' ✗ missed';
      if (ds === todayStr()) cls += ' today-outline';
      return `<td><span class="${cls} ${h.type === 'workout' ? '' : ''}" style="--hc:${h.color}" data-action="cell" data-id="${h.id}" data-date="${ds}" title="${esc(title)}"></span></td>`;
    }).join('');

    return `
      <tr>
        <td class="name-cell">
          <div class="name-inner">
            <span class="ne">${h.emoji}</span>
            <span class="nt">${esc(h.name)}</span>
            <button class="edit-habit" data-action="edit-habit" data-id="${h.id}" title="Edit habit">✏️</button>
          </div>
          <div class="name-sub">
            <span class="streak">🔥 ${streak}</span>
            <span>${h.freq && h.freq.type === 'days' ? h.freq.days.map(d => DAY_NAMES[d]).join(' ') : 'daily'}</span>
          </div>
        </td>
        ${cells}
      </tr>`;
  }).join('');

  $('#view-habits').innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Habits</div>
        <div class="view-sub">Tap a square to mark done · last ${days} days</div>
      </div>
      <div class="toolbar">
        <select class="select" data-action="filter">
          ${cats.map(c => `<option value="${esc(c)}" ${ui.filter === c ? 'selected' : ''}>${c === 'all' ? 'All categories' : esc(c)}</option>`).join('')}
        </select>
        <select class="select" data-action="grid-range">
          ${[30, 60, 90].map(n => `<option value="${n}" ${days === n ? 'selected' : ''}>${n} days</option>`).join('')}
        </select>
        <button class="btn primary small" data-action="add-habit">＋ Habit</button>
      </div>
    </div>

    ${habits.length ? `
    <div class="card">
      <div class="grid-wrap">
        <table class="hgrid">
          <thead><tr><th class="name-cell" style="background:#10162a">Habit</th>${headCells}</tr></thead>
          <tbody>${rows}</tbody>
        </table>
      </div>
      <div class="grid-legend">
        <span><i style="background:#22c55e"></i>done</span>
        <span><i style="background:rgba(34,197,94,.45)"></i>partial</span>
        <span><i style="background:#151c30;border:1px solid #232c45"></i>missed</span>
        <span><i style="background:transparent;border:1px dashed #232c45"></i>rest / future</span>
        <span style="margin-left:auto">🔥 = current streak · ✏️ = edit/delete</span>
      </div>
    </div>` : `<div class="empty"><b>No habits yet.</b><br>Hit <b>＋ Habit</b> to create one.</div>`}
  `;
}

/* ============================================================
   RENDER — STATS
   ============================================================ */
function renderStats() {
  const habits = state.habits;
  const today = new Date();

  // overall last 14 days bars
  const bars = [];
  for (let i = 13; i >= 0; i--) {
    const ds = fmtDate(addDays(today, -i));
    const st = dayStats(ds);
    bars.push({ ds, pct: st.pct });
  }
  const barsHtml = bars.map(b => {
    const d = parseDate(b.ds);
    const pct = b.pct;
    const h = pct === null ? 4 : Math.max(6, Math.round((pct / 100) * 100));
    return `<div class="bar-col" title="${b.ds}: ${pct === null ? 'no habits' : pct + '%'}">
      <div class="bv" style="font-size:9px;color:#8b96b5">${pct ?? ''}</div>
      <div class="bar ${pct === null || pct === 0 ? 'miss' : ''}" style="height:${pct === null ? 4 : Math.max(6, (pct / 100) * 100)}%"></div>
      <div class="bl">${DAYS_SHORT[d.getDay()]}</div>
    </div>`;
  }).join('');

  // per-habit 30 day bars
  const hs = habits.map(h => {
    const pct = completion(h, 30) ?? 0;
    const st = currentStreak(h);
    return { h, pct, st };
  }).sort((a, b) => b.pct - a.pct);

  const hsHtml = hs.map(({ h, pct, st }) => `
    <div class="hs-row" title="${esc(h.name)}: ${pct}% last 30 days, 🔥 ${st}">
      <div class="hs-emoji">${h.emoji}</div>
      <div class="hs-name">${esc(h.name)}</div>
      <div class="hs-track"><i style="width:${pct}%;background:${h.color}"></i></div>
      <div class="hs-pct">${pct}%</div>
      <div class="hs-streak">🔥 ${st}</div>
    </div>`).join('');

  // heatmap last 26 weeks
  const hm = [];
  const end = new Date(today);
  const startCol = addDays(end, -(26 * 7 - 1));
  // align to Monday
  const offset = (startCol.getDay() + 6) % 7;
  let d0 = addDays(startCol, -offset);
  const cellsByCol = [];
  for (let col = 0; col < 27; col++) {
    const column = [];
    for (let row = 0; row < 7; row++) {
      const ds = fmtDate(addDays(d0, col * 7 + row));
      const future = ds > todayStr();
      const st = dayStats(ds);
      let color = '#141b2f';
      let tip = ds;
      if (!future && st.pct !== null) {
        const p = st.pct;
        tip = `${ds} — ${st.done}/${st.due} (${p}%)`;
        if (p === 100) color = '#22c55e';
        else if (p >= 75) color = 'rgba(34,197,94,.72)';
        else if (p >= 50) color = 'rgba(34,197,94,.45)';
        else if (p > 0) color = 'rgba(34,197,94,.25)';
        else color = '#1a2138';
      } else if (future) color = 'transparent';
      column.push(`<div class="hm-cell" style="background:${color}" title="${tip}"></div>`);
    }
    cellsByCol.push(column.join(''));
  }
  const heatmapHtml = cellsByCol.join('');

  // headline stats
  const tSt = dayStats(todayStr());
  let weekDone = 0, weekDue = 0;
  for (let i = 0; i < 7; i++) { const s = dayStats(fmtDate(addDays(today, -i))); weekDue += s.due; weekDone += s.done; }
  const weekPct = weekDue ? Math.round((weekDone / weekDue) * 100) : 0;
  let totalCheckins = 0;
  Object.keys(state.logs).forEach(k => { const l = state.logs[k]; if (l && l.count > 0) totalCheckins++; });
  const best = habits.map(h => ({ h, s: currentStreak(h) })).sort((a, b) => b.s - a.s)[0];

  // PRs
  const prs = usedExercises()
    .map(ex => ({ ex, pr: prFor(ex) }))
    .filter(x => x.pr)
    .sort((a, b) => b.pr.weight - a.pr.weight)
    .slice(0, 8);

  $('#view-stats').innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Stats</div>
        <div class="view-sub">Your consistency, visualized</div>
      </div>
    </div>

    <div class="stat-cards">
      <div class="stat-card"><div class="lbl">Today</div><div class="big">${tSt.pct === null ? '—' : tSt.pct + '%'}</div><div class="sub">${tSt.done}/${tSt.due} habits</div></div>
      <div class="stat-card"><div class="lbl">This week</div><div class="big">${weekPct}%</div><div class="sub">${weekDone}/${weekDue} check-ins</div></div>
      <div class="stat-card"><div class="lbl">Top streak</div><div class="big">🔥 ${best ? best.s : 0}</div><div class="sub">${best ? best.h.emoji + ' ' + esc(best.h.name) : 'no habits'}</div></div>
      <div class="stat-card"><div class="lbl">Total check-ins</div><div class="big">${totalCheckins}</div><div class="sub">all time</div></div>
    </div>

    <div class="card">
      <div class="chart-title">Last 14 days <span class="view-sub">% of due habits completed</span></div>
      <div class="bars">${barsHtml}</div>
    </div>

    <div class="card">
      <div class="chart-title">Consistency map <span class="view-sub">last 6 months</span></div>
      <div class="heatmap">${heatmapHtml}</div>
      <div class="hm-legend">less
        <i style="background:#1a2138"></i><i style="background:rgba(34,197,94,.25)"></i>
        <i style="background:rgba(34,197,94,.45)"></i><i style="background:rgba(34,197,94,.72)"></i>
        <i style="background:#22c55e"></i> more
      </div>
    </div>

    <div class="card">
      <div class="chart-title">Habits · last 30 days</div>
      <div class="habit-stats">${hsHtml || '<div class="ws-empty">No habits yet.</div>'}</div>
    </div>

    ${prs.length ? `
    <div class="card">
      <div class="chart-title">🏋️ Personal records</div>
      <table class="pr-table">
        <thead><tr><th>Exercise</th><th>Best</th><th>Reps</th><th>Date</th></tr></thead>
        <tbody>
          ${prs.map((p, i) => `<tr>
            <td><span class="medal">${i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : '  '}</span> ${esc(p.ex)}</td>
            <td class="pr-val">${p.pr.weight} kg</td><td>${p.pr.reps}</td>
            <td style="color:#8b96b5">${p.pr.date}</td>
          </tr>`).join('')}
        </tbody>
      </table>
    </div>` : ''}
  `;
}

/* ============================================================
   RENDER — WORKOUTS
   ============================================================ */
function renderWorkouts() {
  const sessions = [...state.workouts].sort((a, b) => b.date.localeCompare(a.date));

  const sessionHtml = sessions.map(w => {
    const exHtml = (w.exercises || []).map(e => {
      const pr = prFor(e.name);
      const top = e.sets.reduce((m, s) => Math.max(m, num(s.weight)), 0);
      const isPr = pr && pr.date === w.date && top === pr.weight && top > 0;
      return `<div class="ex-line">
        <span class="ex-name">${esc(e.name)}</span>
        <span class="ex-sets">${e.sets.map(s => `${s.weight}×${s.reps}`).join(' · ')}</span>
        ${isPr ? '<span class="ex-pr">🏆 PR</span>' : ''}
      </div>`;
    }).join('');
    return `
      <div class="session">
        <div class="session-head">
          <div>
            <div class="session-title">${esc(w.title || 'Workout')}</div>
            <div class="session-date">${prettyDate(w.date).main}</div>
          </div>
          <div style="margin-left:auto;display:flex;gap:8px">
            <button class="btn ghost small" data-action="ws-edit" data-id="${w.id}">✏️ Edit</button>
            <button class="btn ghost small" data-action="ws-delete" data-id="${w.id}">🗑</button>
          </div>
        </div>
        <div class="session-stats">
          <span><b>${(w.exercises || []).length}</b> exercises</span>
          <span><b>${(w.exercises || []).reduce((n, e) => n + e.sets.length, 0)}</b> sets</span>
          <span><b>${workoutVolume(w).toLocaleString('en-IN')}</b> kg volume</span>
        </div>
        ${exHtml}
        <div class="session-actions">
          <button class="btn ghost small" data-action="ws-repeat-one" data-id="${w.id}">🔁 Repeat this workout</button>
        </div>
      </div>`;
  }).join('');

  // progression chart
  const exList = usedExercises();
  if (!ui.chartEx || !exList.includes(ui.chartEx)) ui.chartEx = exList[0] || null;
  const chips = exList.map(ex => `<button class="chip ${ui.chartEx === ex ? 'on' : ''}" data-action="chart-ex" data-ex="${esc(ex)}">${esc(ex)}</button>`).join('');
  const hist = ui.chartEx ? exerciseHistory(ui.chartEx) : [];
  const chartHtml = hist.length >= 2 ? lineChart(hist) : `<div class="ws-empty">${hist.length === 1 ? `Only one session logged for <b>${esc(ui.chartEx)}</b> — log more to see the trend.` : 'Log 2+ sessions to see progression.'}</div>`;

  // PR table
  const prs = exList.map(ex => ({ ex, pr: prFor(ex) })).filter(x => x.pr).sort((a, b) => b.pr.weight - a.pr.weight);
  const prHtml = prs.length ? `
    <table class="pr-table">
      <thead><tr><th>Exercise</th><th>Best</th><th>Reps</th><th>On</th></tr></thead>
      <tbody>${prs.map(p => `<tr><td>${esc(p.ex)}</td><td class="pr-val">${p.pr.weight} kg</td><td>${p.pr.reps}</td><td style="color:#8b96b5">${p.pr.date}</td></tr>`).join('')}</tbody>
    </table>` : '<div class="ws-empty">No PRs yet.</div>';

  $('#view-workouts').innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Workouts</div>
        <div class="view-sub">Legend-style training log</div>
      </div>
      <div class="toolbar">
        <button class="btn ghost small" data-action="ws-repeat-last" ${sessions.length ? '' : 'disabled'}>🔁 Repeat last</button>
        <button class="btn primary small" data-action="ws-new">＋ Log Workout</button>
      </div>
    </div>

    ${sessions.length ? sessionHtml : `<div class="empty"><b>No workouts logged yet.</b><br>Hit <b>＋ Log Workout</b> to record your first session — sets, reps & weights.</div>`}

    ${exList.length ? `
    <div class="card" style="margin-top:12px">
      <div class="chart-title">📈 Progression <span class="view-sub">top set weight per session</span></div>
      <div class="ex-chips">${chips}</div>
      ${chartHtml}
    </div>

    <div class="card" style="margin-top:12px">
      <div class="chart-title">🏆 Personal records</div>
      ${prHtml}
    </div>` : ''}
  `;
}

function lineChart(hist) {
  const W = 640, H = 220, padL = 42, padR = 14, padT = 16, padB = 30;
  const vals = hist.map(p => p.weight);
  let min = Math.min(...vals), max = Math.max(...vals);
  if (min === max) { min = Math.max(0, min - 5); max = max + 5; }
  const range = max - min || 1;
  const x = i => padL + (i / Math.max(1, hist.length - 1)) * (W - padL - padR);
  const y = v => padT + (1 - (v - min) / range) * (H - padT - padB);

  const pts = hist.map((p, i) => `${x(i).toFixed(1)},${y(p.weight).toFixed(1)}`).join(' ');
  const grid = [0, .25, .5, .75, 1].map(f => {
    const v = min + f * range;
    const yy = y(v).toFixed(1);
    return `<line x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}" stroke="#1e2740" stroke-width="1"/>
            <text x="${padL - 7}" y="${+yy + 4}" text-anchor="end" font-size="11" fill="#8b96b5">${Math.round(v)}</text>`;
  }).join('');
  const dots = hist.map((p, i) =>
    `<circle cx="${x(i).toFixed(1)}" cy="${y(p.weight).toFixed(1)}" r="4.5" fill="#22c55e" stroke="#0b0f1a" stroke-width="2"><title>${p.date}: ${p.weight} kg</title></circle>`).join('');
  const labels = hist.map((p, i) => {
    const show = hist.length <= 8 || i % Math.ceil(hist.length / 8) === 0 || i === hist.length - 1;
    return show ? `<text x="${x(i).toFixed(1)}" y="${H - 8}" text-anchor="middle" font-size="10" fill="#8b96b5">${p.date.slice(5)}</text>` : '';
  }).join('');

  return `<svg class="linechart" viewBox="0 0 ${W} ${H}" role="img" aria-label="progression chart">
    ${grid}
    <polyline points="${pts}" fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
    ${dots}${labels}
  </svg>`;
}

/* ============================================================
   RENDER — GOALS
   ============================================================ */
function renderGoals() {
  const cards = state.goals.map(g => {
    let current = num(g.current);
    let auto = false;
    if (g.linkExercise) {
      const pr = prFor(g.linkExercise);
      if (pr) { current = pr.weight; auto = true; }
    }
    const pct = g.target > 0 ? clamp(Math.round((current / g.target) * 100), 0, 100) : 0;
    let deadlineTxt = '';
    if (g.deadline) {
      const days = Math.ceil((parseDate(g.deadline) - new Date()) / 86400000);
      deadlineTxt = days > 0 ? `${days} days left` : days === 0 ? 'DUE TODAY' : `${Math.abs(days)} days overdue`;
    }
    const fmt = v => g.unit === '₹' ? inr(v) : Number(v).toLocaleString('en-IN') + (g.unit && g.unit !== '%' ? ' ' + g.unit : g.unit === '%' ? '%' : '');

    return `
      <div class="goal-card">
        <button class="btn ghost small goal-edit" data-action="edit-goal" data-id="${g.id}">✏️</button>
        <div class="g-emoji">${g.emoji || '🎯'}</div>
        <div class="g-title">${esc(g.title)}</div>
        <div class="g-nums"><b>${fmt(current)}</b> / ${fmt(g.target)}</div>
        <div class="goal-track"><i style="width:${pct}%"></i></div>
        <div class="goal-foot">
          <span class="goal-pct">${pct}%</span>
          ${auto ? '<span class="g-auto">auto · from PR</span>' : `<span style="display:flex;gap:6px;align-items:center">
            <button class="btn ghost small" data-action="goal-minus" data-id="${g.id}">−</button>
            <button class="btn ghost small" data-action="goal-plus" data-id="${g.id}">＋</button></span>`}
          <span>${deadlineTxt}</span>
        </div>
      </div>`;
  }).join('');

  $('#view-goals').innerHTML = `
    <div class="view-head">
      <div>
        <div class="view-title">Goals</div>
        <div class="view-sub">Big targets · track them to the finish line</div>
      </div>
      <button class="btn primary small" data-action="add-goal">＋ Goal</button>
    </div>
    ${state.goals.length ? `<div class="goal-grid">${cards}</div>` : `<div class="empty"><b>No goals yet.</b><br>Hit <b>＋ Goal</b> to define your first big target.</div>`}
  `;
}

/* ============================================================
   MODALS — habit form / goal form
   ============================================================ */
let modalCtx = null;

function openModal(html, ctx) {
  modalCtx = ctx || {};
  $('#modalBody').innerHTML = html;
  $('#modalOverlay').classList.add('open');
  const form = $('#modalForm');
  if (form) form.addEventListener('submit', onModalSubmit);
  const first = $('#modalBody input[name="name"]') || $('#modalBody input[type="text"]');
  if (first) setTimeout(() => first.focus(), 60);
}
function closeModal() { $('#modalOverlay').classList.remove('open'); modalCtx = null; }

function habitForm(h) {
  const isNew = !h;
  h = h || {
    emoji: '🎯', name: '', category: 'Health', type: 'check', color: COLORS[0],
    target: 1, unit: '', freq: { type: 'daily', days: [] }
  };
  const days = h.freq && h.freq.type === 'days' ? h.freq.days : [];

  return `
  <h2>${isNew ? 'New habit' : 'Edit habit'}</h2>
  <form id="modalForm" data-kind="habit" data-id="${isNew ? '' : h.id}">
    <div class="field">
      <label>Name</label>
      <input type="text" name="name" maxlength="50" required placeholder="e.g. Cold shower" value="${esc(h.name)}">
    </div>

    <div class="field">
      <span class="flabel">Icon</span>
      <div class="emoji-grid">
        ${EMOJIS.map(e => `<button type="button" data-action="pick-emoji" data-e="${e}" class="${e === h.emoji ? 'on' : ''}">${e}</button>`).join('')}
      </div>
      <input type="hidden" name="emoji" value="${esc(h.emoji)}">
    </div>

    <div class="field">
      <span class="flabel">Color</span>
      <div class="color-grid">
        ${COLORS.map(c => `<button type="button" data-action="pick-color" data-c="${c}" class="${c === h.color ? 'on' : ''}" style="background:${c}"></button>`).join('')}
      </div>
      <input type="hidden" name="color" value="${esc(h.color)}">
    </div>

    <div class="field">
      <label>Category</label>
      <input type="text" name="category" list="catList" maxlength="24" value="${esc(h.category)}">
      <datalist id="catList">${CATEGORIES.map(c => `<option value="${c}">`).join('')}</datalist>
    </div>

    <div class="field">
      <span class="flabel">Type</span>
      <div class="segmented">
        <button type="button" data-action="pick-type" data-t="check"   class="${h.type === 'check' ? 'on' : ''}">✅ Check</button>
        <button type="button" data-action="pick-type" data-t="count"   class="${h.type === 'count' ? 'on' : ''}">🔢 Count</button>
        <button type="button" data-action="pick-type" data-t="workout" class="${h.type === 'workout' ? 'on' : ''}">🏋️ Workout</button>
      </div>
      <input type="hidden" name="type" value="${h.type}">
      <div style="font-size:12px;color:#8b96b5;margin-top:7px" id="typeHint">${
        h.type === 'count' ? 'Track a daily quantity — hours, glasses, pages, steps…'
        : h.type === 'workout' ? 'Linked to the 🏋️ workout log — a logged session marks it done.'
        : 'Simple yes/no habit.'}</div>
    </div>

    <div class="field" id="countFields" ${h.type === 'count' ? '' : 'hidden'}>
      <div class="field-row">
        <div class="field"><label>Daily target</label><input type="number" name="target" min="1" step="1" value="${h.target || 1}"></div>
        <div class="field"><label>Unit</label><input type="text" name="unit" maxlength="12" placeholder="min, glasses, hrs…" value="${esc(h.unit || '')}"></div>
      </div>
    </div>

    <div class="field">
      <span class="flabel">Schedule</span>
      <div class="segmented">
        <button type="button" data-action="pick-freq" data-f="daily" class="${h.freq.type !== 'days' ? 'on' : ''}">Every day</button>
        <button type="button" data-action="pick-freq" data-f="days" class="${h.freq.type === 'days' ? 'on' : ''}">Specific days</button>
      </div>
      <input type="hidden" name="freqType" value="${h.freq.type === 'days' ? 'days' : 'daily'}">
      <div class="day-pick" id="dayPick" ${h.freq.type === 'days' ? '' : 'hidden'}>
        ${[1, 2, 3, 4, 5, 6, 0].map(d => `<button type="button" data-action="pick-day" data-d="${d}" class="${days.includes(d) ? 'on' : ''}">${DAY_NAMES[d]}</button>`).join('')}
      </div>
    </div>

    <div class="modal-actions">
      ${isNew ? '' : `<button type="button" class="btn danger" data-action="delete-habit" data-id="${h.id}">Delete</button>`}
      <button type="submit" class="btn primary">${isNew ? 'Create habit' : 'Save changes'}</button>
    </div>
  </form>`;
}

function goalForm(g) {
  const isNew = !g;
  g = g || { emoji: '🎯', title: '', unit: '', target: 100, current: 0, deadline: '', linkExercise: '' };
  const exs = Array.from(new Set([...EXERCISE_CATALOG, ...usedExercises()])).sort();

  return `
  <h2>${isNew ? 'New goal' : 'Edit goal'}</h2>
  <form id="modalForm" data-kind="goal" data-id="${isNew ? '' : g.id}">
    <div class="field">
      <label>What's the target?</label>
      <input type="text" name="title" maxlength="60" required placeholder="e.g. Bench Press 100 kg" value="${esc(g.title)}">
    </div>
    <div class="field">
      <label>Icon (emoji)</label>
      <input type="text" name="emoji" maxlength="4" value="${esc(g.emoji || '🎯')}">
    </div>
    <div class="field-row">
      <div class="field"><label>Target</label><input type="number" name="target" min="1" step="any" required value="${g.target}"></div>
      <div class="field"><label>Current</label><input type="number" name="current" step="any" value="${g.current}" ${g.linkExercise ? 'disabled' : ''}></div>
      <div class="field"><label>Unit</label><input type="text" name="unit" maxlength="12" placeholder="kg, %, ₹…" value="${esc(g.unit || '')}"></div>
    </div>
    <div class="field">
      <label>Deadline (optional)</label>
      <input type="date" name="deadline" value="${esc(g.deadline || '')}">
    </div>
    <div class="field">
      <label>Auto-track from exercise PR (optional)</label>
      <select name="linkExercise">
        <option value="">— none, manual progress —</option>
        ${exs.map(ex => `<option value="${esc(ex)}" ${g.linkExercise === ex ? 'selected' : ''}>${esc(ex)}</option>`).join('')}
      </select>
      <div style="font-size:12px;color:#8b96b5;margin-top:6px">If selected, this goal's progress follows your best lift automatically.</div>
    </div>
    <div class="modal-actions">
      ${isNew ? '' : `<button type="button" class="btn danger" data-action="delete-goal" data-id="${g.id}">Delete</button>`}
      <button type="submit" class="btn primary">${isNew ? 'Create goal' : 'Save changes'}</button>
    </div>
  </form>`;
}

function onModalSubmit(ev) {
  ev.preventDefault();
  const form = ev.target;
  const kind = form.dataset.kind;
  const id = form.dataset.id;
  const fd = new FormData(form);

  if (kind === 'habit') {
    const freqType = fd.get('freqType');
    let days = [];
    if (freqType === 'days') {
      days = $$('#dayPick button.on').map(b => +b.dataset.d);
      if (!days.length) { toast('Pick at least one day (or choose "Every day")'); return; }
    }
    const type = fd.get('type');
    const data = {
      emoji: fd.get('emoji') || '🎯',
      name: (fd.get('name') || '').trim(),
      category: (fd.get('category') || 'Other').trim() || 'Other',
      color: fd.get('color') || COLORS[0],
      type,
      target: type === 'count' ? Math.max(1, num(fd.get('target'))) : 1,
      unit: type === 'count' ? (fd.get('unit') || '').trim() : '',
      freq: { type: freqType === 'days' ? 'days' : 'daily', days: freqType === 'days' ? days.sort((a, b) => ((a + 6) % 7) - ((b + 6) % 7)) : [] }
    };
    if (!data.name) { toast('Give your habit a name'); return; }
    if (id) {
      const h = habitById(id);
      if (h) Object.assign(h, data);
      toast('Habit updated ✓');
    } else {
      state.habits.push(Object.assign({ id: uid(), createdAt: todayStr() }, data));
      toast(`"${data.name}" created 🔥`);
    }
  } else if (kind === 'goal') {
    const data = {
      emoji: (fd.get('emoji') || '🎯').trim(),
      title: (fd.get('title') || '').trim(),
      target: Math.max(1, num(fd.get('target'))),
      current: num(fd.get('current')),
      unit: (fd.get('unit') || '').trim(),
      deadline: fd.get('deadline') || '',
      linkExercise: fd.get('linkExercise') || ''
    };
    if (!data.title) { toast('Give your goal a title'); return; }
    if (id) {
      const g = state.goals.find(x => x.id === id);
      if (g) Object.assign(g, data);
      toast('Goal updated ✓');
    } else {
      state.goals.push(Object.assign({ id: uid() }, data));
      toast('Goal created 🎯');
    }
  }

  save();
  closeModal();
  render();
}

/* ============================================================
   WORKOUT SHEET
   ============================================================ */
let ws = null; // { id?, date, title, exercises: [{name, sets:[{weight,reps}]}] }

function openWorkoutSheet(workoutId, date) {
  if (workoutId) {
    const w = state.workouts.find(x => x.id === workoutId);
    ws = JSON.parse(JSON.stringify(w));
  } else {
    ws = { id: null, date: date || todayStr(), title: defaultTitle(date || todayStr()), exercises: [] };
  }
  $('#wsOverlay').classList.add('open');
  renderWs();
}
function closeWorkoutSheet() { $('#wsOverlay').classList.remove('open'); ws = null; }

function defaultTitle(ds) {
  const day = parseDate(ds).getDay();
  if (day === 0) return 'Legs';
  if (day === 1 || day === 4) return 'Push';
  if (day === 2 || day === 5) return 'Pull';
  return 'Full Body';
}

function repeatWorkout(source) {
  if (!source) { toast('No workout to repeat'); return; }
  ws = {
    id: null,
    date: todayStr(),
    title: source.title || 'Workout',
    exercises: (source.exercises || []).map(e => ({
      name: e.name,
      sets: e.sets.map(s => ({ weight: s.weight, reps: s.reps }))
    }))
  };
  $('#wsOverlay').classList.add('open');
  renderWs();
  toast('Repeated "' + (source.title || 'workout') + '" — sets prefilled, uncheck nothing, just edit ✏️');
}

function renderWs() {
  if (!ws) return;
  const totalSets = ws.exercises.reduce((n, e) => n + e.sets.length, 0);
  const vol = ws.exercises.reduce((v, e) => v + e.sets.reduce((s, x) => s + num(x.weight) * num(x.reps), 0), 0);
  const catalog = Array.from(new Set([...EXERCISE_CATALOG, ...usedExercises()])).sort();
  const existing = state.workouts.some(w => w.id === ws.id);
  const habitDue = state.habits.some(h => h.type === 'workout' && isDue(h, ws.date));

  const exHtml = ws.exercises.map((e, i) => `
    <div class="ws-ex">
      <div class="ws-ex-head">
        <span class="ws-ex-name">${esc(e.name)}</span>
        <button class="btn ghost small" data-action="ws-dup-ex" data-ex="${i}" title="Duplicate">⧉</button>
        <button class="set-del" data-action="ws-del-ex" data-ex="${i}" title="Remove exercise">🗑</button>
      </div>
      <div class="ws-sets-head"><span>#</span><span>kg</span><span>reps</span><span></span></div>
      ${e.sets.map((s, j) => `
        <div class="set-row">
          <span class="snum">${j + 1}</span>
          <input type="number" inputmode="decimal" step="0.5" min="0" value="${s.weight}" data-ex="${i}" data-set="${j}" data-field="weight" aria-label="weight">
          <input type="number" inputmode="numeric" step="1" min="0" value="${s.reps}" data-ex="${i}" data-set="${j}" data-field="reps" aria-label="reps">
          <button class="set-del" data-action="ws-del-set" data-ex="${i}" data-set="${j}">✕</button>
        </div>`).join('')}
      <button class="ws-addset" data-action="ws-add-set" data-ex="${i}">＋ Set ${e.sets.length ? `(copy ${e.sets[e.sets.length - 1].weight}×${e.sets[e.sets.length - 1].reps})` : ''}</button>
    </div>`).join('');

  $('#wsSheet').innerHTML = `
    <div class="ws-head">
      <h2>${existing ? '✏️ Edit workout' : '🏋️ Log workout'}</h2>
      <button class="modal-close" style="position:static" data-action="ws-close">✕</button>
    </div>

    <div class="field-row">
      <div class="field" style="flex:1"><label>Date</label><input type="date" id="wsDate" value="${ws.date}" max="${todayStr()}"></div>
      <div class="field" style="flex:1.4"><label>Title</label><input type="text" id="wsTitle" maxlength="40" value="${esc(ws.title || '')}" placeholder="Push / Pull / Legs…"></div>
    </div>

    ${habitDue ? `<div style="font-size:12.5px;color:#86efac;background:rgba(34,197,94,.1);border:1px solid rgba(34,197,94,.3);padding:8px 11px;border-radius:10px;margin-bottom:13px">💾 Saving this session automatically marks your <b>🏋️ Gym Workout</b> habit done for that day.</div>` : ''}

    ${exHtml || `<div class="ws-empty">Add your first exercise below 👇</div>`}

    <div class="ws-addex">
      <select class="select" id="wsExPicker" style="flex:1">
        <option value="">Choose exercise…</option>
        ${catalog.map(c => `<option value="${esc(c)}">${esc(c)}</option>`).join('')}
        <option value="__custom">＋ Custom exercise…</option>
      </select>
      <button class="btn small" data-action="ws-add-ex">Add</button>
    </div>

    <div class="ws-vol"><b>${totalSets}</b> sets · <b>${Math.round(vol).toLocaleString('en-IN')}</b> kg total volume</div>

    <div class="ws-foot">
      <button class="btn ghost" data-action="ws-close">Cancel</button>
      <button class="btn primary" data-action="ws-save">💾 Save workout</button>
    </div>`;

  $('#wsDate').addEventListener('change', e => { ws.date = e.target.value || todayStr(); renderWs(); });
  $('#wsTitle').addEventListener('input', e => { ws.title = e.target.value; });
  $$('#wsSheet input[data-field]').forEach(inp => {
    inp.addEventListener('input', e => {
      const i = +e.target.dataset.ex, j = +e.target.dataset.set, f = e.target.dataset.field;
      if (ws.exercises[i] && ws.exercises[i].sets[j]) ws.exercises[i].sets[j][f] = num(e.target.value);
    });
  });
}

function wsAddExercise() {
  const sel = $('#wsExPicker');
  let name = sel.value;
  if (!name) { toast('Pick an exercise first'); return; }
  if (name === '__custom') {
    name = (prompt('Exercise name:') || '').trim();
    if (!name) return;
  }
  // if already present, just add a set
  const found = ws.exercises.find(e => e.name.toLowerCase() === name.toLowerCase());
  if (found) {
    const last = found.sets[found.sets.length - 1] || { weight: 20, reps: 10 };
    found.sets.push({ weight: last.weight, reps: last.reps });
  } else {
    const pr = prFor(name);
    const guess = pr ? pr.weight : 20;
    ws.exercises.push({ name, sets: [{ weight: guess, reps: 10 }] });
  }
  renderWs();
}

function wsSave() {
  if (!ws.exercises.length) { toast('Add at least one exercise'); return; }
  ws.exercises = ws.exercises.filter(e => e.sets.length);
  if (!ws.exercises.length) { toast('Each exercise needs at least one set'); return; }
  const data = {
    id: ws.id || uid(),
    date: ws.date,
    title: (ws.title || 'Workout').trim() || 'Workout',
    exercises: ws.exercises
  };
  const idx = state.workouts.findIndex(w => w.id === data.id);
  if (idx >= 0) state.workouts[idx] = data;
  else state.workouts.push(data);
  save();
  closeWorkoutSheet();
  render();
  toast('Workout saved 💪');
}

/* ============================================================
   EXPORT / IMPORT / RESET
   ============================================================ */
function download(filename, text, mime) {
  const blob = new Blob([text], { type: mime || 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
}
function exportJson() {
  download(`momentum-backup-${todayStr()}.json`, JSON.stringify(state, null, 2));
  toast('Backup downloaded ⬇');
}
function exportCsv() {
  const rows = [['date', 'habit', 'category', 'count', 'target', 'done']];
  Object.keys(state.logs).sort().forEach(k => {
    const [hid, ds] = k.split('|');
    const h = habitById(hid);
    if (!h) return;
    const c = num(state.logs[k].count);
    rows.push([ds, h.name, h.category, c, h.target || 1, c >= (h.target || 1) ? 'yes' : 'no']);
  });
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(',')).join('\n');
  download(`momentum-logs-${todayStr()}.csv`, csv, 'text/csv');
  toast('CSV downloaded ⬇');
}
function importJson(file) {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const data = JSON.parse(reader.result);
      if (!data || !Array.isArray(data.habits)) throw new Error('bad file');
      state = Object.assign(seedState(), data);
      state.logs = state.logs || {}; state.notes = state.notes || {};
      state.workouts = state.workouts || []; state.goals = state.goals || [];
      save(); render();
      toast('Data imported ✓');
    } catch (e) { toast('Import failed — not a valid Momentum backup'); }
  };
  reader.readAsText(file);
}
function resetAll() {
  if (!confirm('Wipe ALL habits, logs, workouts and goals and start fresh? This cannot be undone unless you exported a backup.')) return;
  state = seedState();
  save(); render();
  toast('Fresh start 🌱');
}

/* ============================================================
   TABS / EVENT WIRING
   ============================================================ */
function setTab(tab) {
  ui.tab = tab;
  $$('.bottomnav button').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  $$('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + tab));
  render();
}
function render() {
  if (ui.tab === 'today') renderToday();
  else if (ui.tab === 'habits') renderHabits();
  else if (ui.tab === 'stats') renderStats();
  else if (ui.tab === 'workouts') renderWorkouts();
  else if (ui.tab === 'goals') renderGoals();
}

document.addEventListener('click', ev => {
  const el = ev.target.closest('[data-action]');
  if (!el) return;
  const a = el.dataset.action;
  const id = el.dataset.id;
  const ds = el.dataset.date;

  switch (a) {
    /* nav */
    case 'nav': setTab(el.dataset.tab); break;

    /* today */
    case 'date-prev': ui.date = fmtDate(addDays(parseDate(ui.date), -1)); render(); break;
    case 'date-next': if (ui.date < todayStr()) { ui.date = fmtDate(addDays(parseDate(ui.date), 1)); render(); } break;
    case 'date-today': ui.date = todayStr(); render(); break;
    case 'toggle-habit': { const h = habitById(id); if (h) { toggleHabit(h, ds); render(); } break; }
    case 'count-inc': { const h = habitById(id); if (h) { adjustCount(h, ds, 1); render(); } break; }
    case 'count-dec': { const h = habitById(id); if (h) { adjustCount(h, ds, -1); render(); } break; }
    case 'open-workout': openWorkoutSheet(null, ds); break;

    /* grid */
    case 'cell': {
      const h = habitById(id);
      if (h && h.type === 'workout') { openWorkoutSheet(null, ds); }
      else if (h) { toggleHabit(h, ds); render(); }
      break;
    }

    /* habit CRUD */
    case 'add-habit': openModal(habitForm(null), { kind: 'habit' }); break;
    case 'edit-habit': { const h = habitById(id); if (h) openModal(habitForm(h), { kind: 'habit', id }); break; }
    case 'delete-habit': {
      const h = habitById(id);
      if (h && confirm(`Delete "${h.name}" and all its history?`)) {
        state.habits = state.habits.filter(x => x.id !== id);
        Object.keys(state.logs).forEach(k => { if (k.startsWith(id + '|')) delete state.logs[k]; });
        save(); closeModal(); render(); toast('Habit deleted');
      }
      break;
    }

    /* habit form pickers */
    case 'pick-emoji': { $('input[name="emoji"]', $('#modalBody')).value = el.dataset.e; $$('.emoji-grid button', $('#modalBody')).forEach(b => b.classList.toggle('on', b === el)); break; }
    case 'pick-color': { $('input[name="color"]', $('#modalBody')).value = el.dataset.c; $$('.color-grid button', $('#modalBody')).forEach(b => b.classList.toggle('on', b === el)); break; }
    case 'pick-type': {
      const t = el.dataset.t;
      $('input[name="type"]', $('#modalBody')).value = t;
      $$('.segmented [data-action="pick-type"]', $('#modalBody')).forEach(b => b.classList.toggle('on', b.dataset.t === t));
      $('#countFields').hidden = t !== 'count';
      $('#typeHint').textContent = t === 'count' ? 'Track a daily quantity — hours, glasses, pages, steps…'
        : t === 'workout' ? 'Linked to the 🏋️ workout log — a logged session marks it done.'
        : 'Simple yes/no habit.';
      break;
    }
    case 'pick-freq': {
      const f = el.dataset.f;
      $('input[name="freqType"]', $('#modalBody')).value = f;
      $$('[data-action="pick-freq"]', $('#modalBody')).forEach(b => b.classList.toggle('on', b.dataset.f === f));
      $('#dayPick').hidden = f !== 'days';
      break;
    }
    case 'pick-day': el.classList.toggle('on'); break;

    /* goals */
    case 'add-goal': openModal(goalForm(null), { kind: 'goal' }); break;
    case 'edit-goal': { const g = state.goals.find(x => x.id === id); if (g) openModal(goalForm(g), { kind: 'goal', id }); break; }
    case 'delete-goal': {
      if (id && confirm('Delete this goal?')) { state.goals = state.goals.filter(g => g.id !== id); save(); closeModal(); render(); toast('Goal deleted'); }
      break;
    }
    case 'goal-plus': case 'goal-minus': {
      const g = state.goals.find(x => x.id === id);
      if (g && !g.linkExercise) {
        const step = g.target >= 1000000 ? 100000 : g.target >= 10000 ? 1000 : g.target >= 1000 ? 10 : 1;
        g.current = clamp(num(g.current) + (a === 'goal-plus' ? step : -step), 0, g.target * 10);
        save(); render();
      } else if (g && g.linkExercise) toast('This goal auto-updates from your PRs 🏆');
      break;
    }

    /* workouts */
    case 'ws-new': openWorkoutSheet(null, todayStr()); break;
    case 'ws-edit': openWorkoutSheet(id); break;
    case 'ws-repeat-last': repeatWorkout([...state.workouts].sort((x, y) => y.date.localeCompare(x.date))[0]); break;
    case 'ws-repeat-one': repeatWorkout(state.workouts.find(w => w.id === id)); break;
    case 'ws-close': closeWorkoutSheet(); break;
    case 'ws-save': wsSave(); break;
    case 'ws-add-ex': wsAddExercise(); break;
    case 'ws-del-ex': { ws.exercises.splice(+el.dataset.ex, 1); renderWs(); break; }
    case 'ws-dup-ex': { const e2 = ws.exercises[+el.dataset.ex]; ws.exercises.splice(+el.dataset.ex + 1, 0, JSON.parse(JSON.stringify(e2))); renderWs(); break; }
    case 'ws-add-set': {
      const e2 = ws.exercises[+el.dataset.ex];
      const last = e2.sets[e2.sets.length - 1] || { weight: 20, reps: 10 };
      e2.sets.push({ weight: last.weight, reps: last.reps });
      renderWs();
      break;
    }
    case 'ws-del-set': { ws.exercises[+el.dataset.ex].sets.splice(+el.dataset.set, 1); renderWs(); break; }
    case 'ws-delete': {
      if (confirm('Delete this workout session?')) {
        state.workouts = state.workouts.filter(w => w.id !== id);
        save(); render(); toast('Workout deleted');
      }
      break;
    }

    /* misc */
    case 'chart-ex': ui.chartEx = el.dataset.ex; render(); break;
    case 'export': exportJson(); break;
    case 'import': $('#importFile').click(); break;
    case 'close-modal': closeModal(); break;
  }
});

/* selects & file input */
document.addEventListener('change', ev => {
  const el = ev.target;
  if (el.dataset && el.dataset.action === 'grid-range') { ui.gridDays = +el.value; render(); }
  else if (el.dataset && el.dataset.action === 'filter') { ui.filter = el.value; render(); }
  else if (el.id === 'importFile' && el.files && el.files[0]) { importJson(el.files[0]); el.value = ''; }
});

/* close overlays on backdrop / Esc */
$('#modalOverlay').addEventListener('click', e => { if (e.target.id === 'modalOverlay') closeModal(); });
$('#wsOverlay').addEventListener('click', e => { if (e.target.id === 'wsOverlay') closeWorkoutSheet(); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeModal(); closeWorkoutSheet(); }
});

/* live clock: roll over to a new day if the app stays open past midnight */
setInterval(() => {
  if (ui.tab === 'today' && ui.date === todayStr()) render();
}, 60000);

/* boot */
render();
if (!stateLoaded) setTimeout(() => toast('Welcome 🔥 Seeded starter habits — edit or delete them to make it yours.'), 400);
