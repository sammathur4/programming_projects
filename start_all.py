#!/usr/bin/env python3
"""Start the local stack, plus a public URL for Mission 2026.

    python3 start_all.py             start everything
    python3 start_all.py status      what is up, and the public Mission 2026 URL
    python3 start_all.py stop        stop everything
    python3 start_all.py --dry-run   print the commands, run nothing
    python3 start_all.py --self-check  verify the port probe

IASCode      docker compose — backend :8000, frontend :5173
WhatsApp bot whatsapp_bot/run.sh — Chrome, DISPLAY, QR all handled there
Mission 2026 mission2026/run_server.sh :8001, published over an ssh reverse
             tunnel (localhost.run) so it opens from any network, no account
"""

import os
import re
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UPSC = ROOT / "upsc_app"
BOT = ROOT / "whatsapp_bot"
MISSION = ROOT / "mission2026"
RUN = MISSION / ".run"  # gitignored logs + pids
MISSION_PORT = 8001
TUNNEL_URL = re.compile(r"https://[a-z0-9]+\.lhr\.life")
PORTS = {
    3000: "WhatsApp bot",
    5173: "IASCode frontend",
    8000: "IASCode backend",
    8001: "Mission 2026",
}
DRY = "--dry-run" in sys.argv


def run(cmd, cwd):
    print(f"$ {' '.join(cmd)}  (in {cwd.relative_to(ROOT)})", flush=True)
    return 0 if DRY else subprocess.run(cmd, cwd=cwd).returncode


def spawn(cmd, cwd, name):
    """Background process in its own session, so stop can take the whole tree."""
    log = RUN / f"{name}.log"
    print(f"$ {' '.join(cmd)}  (in {cwd.relative_to(ROOT)}) > {log}", flush=True)
    if DRY:
        return
    RUN.mkdir(exist_ok=True)
    with open(log, "ab") as out:
        proc = subprocess.Popen(
            cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL, start_new_session=True,
        )
    (RUN / f"{name}.pid").write_text(str(proc.pid))


def alive(name):
    try:
        os.kill(int((RUN / f"{name}.pid").read_text()), 0)
        return True
    except (OSError, ValueError):
        return False


def kill(name):
    pidfile = RUN / f"{name}.pid"
    if not alive(name):
        pidfile.unlink(missing_ok=True)
        return
    pid = int(pidfile.read_text())
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(pid, sig)
        except OSError:
            break
        time.sleep(1)
        if not alive(name):
            break
    pidfile.unlink(missing_ok=True)
    print(f"stopped {name} (pid {pid})")


def up(port):
    try:
        with socket.create_connection(("127.0.0.1", port), 1):
            return True
    except OSError:
        return False


def wait_port(port, seconds=25):
    for _ in range(seconds):
        if up(port):
            return True
        time.sleep(1)
    return up(port)


def tunnel_url():
    log = RUN / "tunnel.log"
    if not log.exists():
        return None
    found = TUNNEL_URL.findall(log.read_text(errors="replace"))
    return found[-1] if found else None


def start():
    # bash explicitly: the drive is NTFS, exec bits do not survive.
    if run(["docker", "compose", "up", "-d"], UPSC) != 0:
        print("! docker compose failed — see the error above.")
    run(["bash", "run.sh", "bg"], BOT)

    if not up(MISSION_PORT) and not DRY:
        spawn(["bash", "run_server.sh", str(MISSION_PORT)], MISSION, "mission")
        wait_port(MISSION_PORT)

    if not alive("tunnel"):
        # Free localhost.run tunnel: random https://<id>.lhr.life URL per
        # session, dies with the ssh process. ponytail: fine for a personal
        # app; move to ngrok with a reserved domain if the URL must be stable.
        (RUN / "tunnel.log").unlink(missing_ok=True)
        spawn(
            ["ssh", "-n", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
             "-o", "ExitOnForwardFailure=yes", "-o", "ServerAliveInterval=20",
             "-R", f"80:localhost:{MISSION_PORT}", "nokey@localhost.run"],
            ROOT, "tunnel",
        )
        for _ in range(30):
            if tunnel_url():
                break
            time.sleep(1)

    print()
    down = status()
    if down:
        print(f"\nStill down: {', '.join(down)}")
        return 1
    return 0


def stop():
    kill("tunnel")
    kill("mission")
    run(["bash", "run.sh", "stop"], BOT)
    run(["docker", "compose", "down"], UPSC)
    return 0


def status():
    down = []
    for port, name in sorted(PORTS.items()):
        live = up(port)
        print(f"{'up  ' if live else 'DOWN'}  :{port:<5} {name}")
        if not live:
            down.append(name)
    url = tunnel_url()
    if up(MISSION_PORT):
        print(f"      local  http://localhost:{MISSION_PORT}/")
        if url and alive("tunnel"):
            print(f"      public {url}/")
        else:
            print("      public — (tunnel not running: python3 start_all.py)")
        print("      bot    MISSION_API_URL should be "
              f"http://localhost:{MISSION_PORT}/api")
    return down


def self_check():
    assert not up(1), "port 1 should be closed"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        assert up(port), f"own listening socket on {port} not detected"
    print("self-check ok")


if __name__ == "__main__":
    cmd = next((a for a in sys.argv[1:] if not a.startswith("-")), "start")
    if "--self-check" in sys.argv:
        self_check()
    elif cmd == "status":
        sys.exit(1 if status() else 0)
    elif cmd == "stop":
        sys.exit(stop())
    elif cmd == "start":
        sys.exit(start())
    else:
        sys.exit(f"unknown command: {cmd} (start|stop|status)")
