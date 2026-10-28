// Pull every pin from the board by replaying the page's own BoardFeedResource
// request shape (react_grid_pin + redux_normalize_feed + bookmarks), paginating.
const CDP_PORT = 9333;
const USERNAME = "sammathur4";
const SLUG = "01-vision-board-2026";
const BOARD_ID = "286049082521634823";
const BOARD_URL = `https://www.pinterest.com/${USERNAME}/${SLUG}/`;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  let targets = [];
  for (let i = 0; i < 60; i++) {
    try {
      targets = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json();
      if (targets.some((t) => t.type === "page")) break;
    } catch {}
    await sleep(500);
  }
  const page = targets.find((t) => t.type === "page");
  if (!page) throw new Error("no page target");

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  ws.addEventListener("message", (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const { resolve, reject } = pending.get(m.id);
      pending.delete(m.id);
      m.error ? reject(new Error(JSON.stringify(m.error))) : resolve(m.result);
    }
  });
  await new Promise((r) => ws.addEventListener("open", r));
  const send = (mth, p = {}) =>
    new Promise((res, rej) => {
      const mid = ++id;
      pending.set(mid, { resolve: res, reject: rej });
      ws.send(JSON.stringify({ id: mid, method: mth, params: p }));
    });

  await send("Page.enable");
  await send("Runtime.enable");
  await send("Page.navigate", { url: BOARD_URL });
  await sleep(11000);

  const ev = async (expr) => {
    const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 400));
    return r.result.value;
  };

  console.error("logged_in:", await ev(`!document.querySelector('[data-test-id="login-button"]')`));

  const script = `
    (async () => {
      const sleep = (ms) => new Promise(r => setTimeout(r, ms));
      const csrf = (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || "";
      const headers = {
        "Accept": "application/json, text/javascript, */*, q=0.01",
        "X-Requested-With": "XMLHttpRequest",
        "X-Pinterest-AppState": "active",
        "X-Pinterest-Source-Url": "/${USERNAME}/${SLUG}/",
        "X-Pinterest-PWS-Handler": "www/[username]/[slug].js",
        "X-APP-Version": "23e4fdc",
        "X-CSRFToken": csrf,
      };
      const seen = new Map();
      let bookmark = null;
      let lastErr = null;

      for (let page = 0; page < 40; page++) {
        const options = {
          board_id: "${BOARD_ID}",
          board_url: "/${USERNAME}/${SLUG}/",
          currentFilter: -1,
          field_set_key: "react_grid_pin",
          filter_section_pins: true,
          sort: "default",
          layout: "default",
          page_size: 25,
          redux_normalize_feed: true,
        };
        if (bookmark) options.bookmarks = [bookmark];
        const data = { options, context: {} };
        const url = "/resource/BoardFeedResource/get/?source_url=" +
          encodeURIComponent("/${USERNAME}/${SLUG}/") +
          "&data=" + encodeURIComponent(JSON.stringify(data));

        let j;
        try {
          const r = await fetch(url, { headers, credentials: "include" });
          const text = await r.text();
          try { j = JSON.parse(text); }
          catch { lastErr = "non-json " + r.status + " " + text.slice(0,120); break; }
        } catch (e) { lastErr = "fetch " + e.message; break; }

        const rr = j.resource_response || {};
        const d = rr.data || [];
        for (const p of d) {
          if (!p || !p.id) continue;
          if (p.type === "story") continue;
          seen.set(p.id, p);
        }
        const bm = rr.bookmark ||
          (j.resource && j.resource.options && j.resource.options.bookmarks
            ? j.resource.options.bookmarks[0] : null);
        bookmark = Array.isArray(bm) ? bm[0] : bm;
        if (!bookmark) break;
        await sleep(650);
      }

      const pins = [...seen.values()].map((p, i) => {
        const im = p.images || {};
        const best = im.orig || im["736x"] || im["564x"] || im["474x"] || im["236x"] || {};
        return {
          order: i,
          id: p.id,
          title: (p.title || p.grid_title || "").trim(),
          description: (p.description || "").trim(),
          alt: (p.alt_text || "").trim(),
          link: p.link || "",
          domain: p.domain || "",
          image: best.url || "",
          width: best.width || 0,
          height: best.height || 0,
        };
      });
      return { total: pins.length, lastErr, pins };
    })()
  `;

  console.log(JSON.stringify(await ev(script), null, 1));
  ws.close();
}
main().catch((e) => { console.error("ERR", e.message); process.exit(1); });
