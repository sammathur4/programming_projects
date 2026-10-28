#!/usr/bin/env python3
"""Reliable full-page render + layout metrics for the vision board (via CDP).

Usage:
    python3 render_vision_board_previews.py vision_board/index.html

Writes preview-light.png / preview-dark.png (top of page, both themes) next to
the HTML and prints layout stats (page height, image load count, card sizes).
Needs: google-chrome, python 'websockets'.
"""
import asyncio, base64, json, os, re, subprocess, sys, time, urllib.request

import websockets

OUTDIR = None  # set in main()

PORT = 9333


def launch():
    proc = subprocess.Popen(
        [
            "google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox",
            "--hide-scrollbars", f"--remote-debugging-port={PORT}",
            "--user-data-dir=/tmp/opencode/cdp-profile", "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1).read()
            return proc
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("chrome did not start")


def new_target():
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/json/new?about:blank", method="PUT")
    return json.loads(urllib.request.urlopen(req, timeout=5).read())


class CDP:
    def __init__(self, ws):
        self.ws, self.n = ws, 0

    async def call(self, method, **params):
        self.n += 1
        mid = self.n
        await self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(await self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    async def eval(self, expr):
        r = await self.call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
        return r.get("result", {}).get("value")


async def render(url, png, width=1500, full=True, scale=0.6, clip_h=14000):
    target = new_target()
    async with websockets.connect(target["webSocketDebuggerUrl"], max_size=200 * 1024 * 1024) as ws:
        c = CDP(ws)
        await c.call("Page.enable")
        await c.call("Runtime.enable")
        await c.call("Emulation.setDeviceMetricsOverride", width=width, height=1000,
                     deviceScaleFactor=1, mobile=False)
        await c.call("Page.navigate", url=url)
        for _ in range(80):
            await asyncio.sleep(0.25)
            if await c.eval("document.readyState") == "complete":
                break
        # force every image to load (defeat lazy-loading for measurement)
        await c.eval("document.querySelectorAll('img').forEach(function(i){i.loading='eager';});"
                     "document.querySelectorAll('.reveal').forEach(function(e){e.classList.add('in');});")
        for _ in range(120):
            st = await c.eval(
                "JSON.stringify({t:document.images.length,"
                "ok:[].filter.call(document.images,function(i){return i.complete&&i.naturalWidth>0}).length})"
            )
            st = json.loads(st)
            if st["ok"] >= st["t"]:
                break
            await asyncio.sleep(0.25)
        await asyncio.sleep(1.5)
        stats = json.loads(await c.eval("""
          JSON.stringify({
            images:document.images.length,
            loaded:[].filter.call(document.images,function(i){return i.complete&&i.naturalWidth>0}).length,
            broken:[].filter.call(document.images,function(i){return i.complete&&i.naturalWidth===0}).length,
            pageHeight:document.body.scrollHeight,
            theme:document.documentElement.dataset.theme,
            cards:document.querySelectorAll('.card').length,
            galleries:[].map.call(document.querySelectorAll('.gallery'),function(g){
              var r=g.getBoundingClientRect();
              return {n:g.querySelectorAll('img').length,h:Math.round(r.height),
                      w:Math.round(r.width),top:Math.round(r.top+scrollY)};}),
            cardsM:[].map.call(document.querySelectorAll('.card'),function(e){
              var r=e.getBoundingClientRect();return {id:e.id,top:Math.round(r.top+scrollY),h:Math.round(r.height)};})
          })"""))
        h = stats["pageHeight"]
        clip = {"x": 0, "y": 0, "width": width, "height": min(h, clip_h), "scale": scale}
        shot = await c.call("Page.captureScreenshot", format="png",
                            captureBeyondViewport=True, clip=clip)
        open(png, "wb").write(base64.b64decode(shot["data"]))
        await c.call("Page.close")
        return stats


async def main():
    global OUTDIR
    OUTDIR = os.path.dirname(os.path.abspath(sys.argv[1]))
    proc = launch()
    try:
        for theme in ("light", "dark"):
            url = f"file://{os.path.abspath(sys.argv[1])}?theme={theme}"
            clip_h, scale, suffix = int(os.environ.get("CLIP_H", 14000)), float(os.environ.get("SCALE", 0.6)), os.environ.get("SUFFIX", "")
            stats = await render(url, f"{OUTDIR}/preview-{theme}{suffix}.png", scale=scale, clip_h=clip_h)
            print(f"--- {theme} ---")
            print(f"  theme={stats['theme']} images={stats['loaded']}/{stats['images']} "
                  f"broken={stats['broken']} pageHeight={stats['pageHeight']} cards={stats['cards']}")
            tall = sorted(stats["galleries"], key=lambda g: g["h"], reverse=True)[:6]
            print("  tallest galleries:", [(g["n"], g["h"]) for g in tall])
            hs = [c["h"] for c in stats["cardsM"]]
            print(f"  card heights: min={min(hs)} max={max(hs)} median={sorted(hs)[len(hs)//2]}")
    finally:
        proc.terminate()


asyncio.run(main())
