#!/usr/bin/env python3
"""
optimize_mint.py - one-shot tuning for this Linux Mint laptop.

Lives inside the single coding workspace:
  /media/saksham/phone data/programming_projects/optimize_mint/

HARD PROTECTIONS (enforced in code, no flag can override them)
  * <workspace>/whatsapp_bot
  * any process whose cmdline/cwd/open files reference whatsapp_bot, wwebjs
    or its headless-chrome profile  -> never killed, never moved, never cached-out
  * /home/saksham/Downloads/Telegram
  * /home/saksham/Desktop/listen and /home/saksham/Desktop/wallpapers
  * the opencode server that is running THIS session (ancestor PID protection)

This script never moves code out of the workspace. All projects stay here.

USAGE
  python3 optimize_mint.py --list            show tasks
  python3 optimize_mint.py --dry-run         print every command, change nothing
  python3 optimize_mint.py                   interactive, asks per task
  python3 optimize_mint.py --yes             run everything without asking
  python3 optimize_mint.py --only swap,boot  run a subset
  python3 optimize_mint.py --skip docker     run all but some
  python3 optimize_mint.py --include-risky   also prune tagged docker images,
                                             stopped containers, kill the
                                             duplicate opencode pairing server

Run it as your normal user (not root). It calls sudo only where needed and
will prompt once for your password.
"""

from __future__ import annotations

import argparse
import glob
import os
import re
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

# --------------------------------------------------------------------------
# paths / protection
# --------------------------------------------------------------------------

if os.geteuid() == 0 and os.environ.get("SUDO_USER"):
    import pwd

    HOME = Path(pwd.getpwnam(os.environ["SUDO_USER"]).pw_dir)
else:
    HOME = Path.home()

NTFS_ROOT = Path("/media/saksham/phone data")

# Resolve the workspace from this file so no hard-coded /media path is needed.
# Handles the script living either in the workspace root or one folder below it.
_here = Path(__file__).resolve().parent
if (_here / "whatsapp_bot").is_dir():
    WORKSPACE = _here
elif (_here.parent / "whatsapp_bot").is_dir():
    WORKSPACE = _here.parent
else:  # fallback if someone copies the script out of the workspace
    WORKSPACE = NTFS_ROOT / "programming_projects"

PROTECTED_PATHS = [
    WORKSPACE / "whatsapp_bot",
    HOME / "Downloads" / "Telegram",
    HOME / "Desktop" / "listen",
    HOME / "Desktop" / "wallpapers",
]

# substrings that mark a process as "do not touch" (in addition to PROTECTED_PATHS)
PROTECTED_CMDLINE_MARKERS = (
    "whatsapp_bot",
    "wwebjs",
    ".wwebjs_auth",
)

LOG_DIR = HOME / ".local/state/optimize-mint"
LOG_PATH = LOG_DIR / f"run-{datetime.now():%Y%m%d-%H%M%S}.log"
_log_handle = None

DRY = False
YES = False
INCLUDE_RISKY = False

REBOOT_NEEDED: list[str] = []
MANUAL: list[str] = []


# --------------------------------------------------------------------------
# logging / execution helpers
# --------------------------------------------------------------------------


def log(msg: str = "") -> None:
    global _log_handle
    print(msg, flush=True)
    try:
        if _log_handle is None:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            _log_handle = LOG_PATH.open("a")
        _log_handle.write(msg + "\n")
        _log_handle.flush()
    except OSError:
        pass


def run(cmd: list[str], root: bool = False, timeout: int | None = 120,
        input_text: str | None = None) -> subprocess.CompletedProcess:
    """Read-only probe. Always executes, even in dry-run.

    In dry-run mode privileged probes use `sudo -n` so the script never stops
    to ask for a password just to print a report.
    """
    full = ((["sudo", "-n"] if DRY else ["sudo"]) + cmd) if root else cmd
    try:
        return subprocess.run(full, input=input_text, text=True,
                              capture_output=True, timeout=timeout)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def do(cmd: list[str], root: bool = False, timeout: int | None = 900,
       quiet: bool = False) -> subprocess.CompletedProcess:
    """Mutating command. Respects --dry-run."""
    printable = " ".join(shlex.quote(c) for c in cmd)
    prefix = "sudo " if root else ""
    if DRY:
        log(f"  [dry-run] {prefix}{printable}")
        return subprocess.CompletedProcess(cmd, 0, "", "")
    log(f"  $ {prefix}{printable}")
    try:
        cp = subprocess.run((["sudo"] + cmd) if root else cmd,
                            text=True, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"  ! timed out after {timeout}s")
        return subprocess.CompletedProcess(cmd, 124, "", "timeout")
    except FileNotFoundError as exc:
        log(f"  ! command not found: {exc}")
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))

    if not quiet and cp.stdout.strip():
        for line in cp.stdout.strip().splitlines()[:12]:
            log(f"    {line}")
    if cp.returncode != 0 and cp.stderr.strip():
        for line in cp.stderr.strip().splitlines()[:6]:
            log(f"    ! {line}")
    return cp


def write_root(path: str | Path, content: str, mode: int = 0o644) -> None:
    if DRY:
        log(f"  [dry-run] write {path}")
        return
    log(f"  $ write {path}")
    try:
        subprocess.run(["sudo", "tee", str(path)], input=content,
                       text=True, capture_output=True, check=True)
        subprocess.run(["sudo", "chmod", oct(mode)[2:], str(path)],
                       capture_output=True)
    except subprocess.CalledProcessError as exc:
        log(f"  ! failed to write {path}: {exc}")


def backup_root(path: str | Path) -> None:
    p = Path(path)
    if not p.exists():
        return
    bak = p.with_suffix(p.suffix + f".bak-{datetime.now():%Y%m%d%H%M%S}")
    do(["cp", "-a", str(p), str(bak)], root=True, quiet=True)


def guard(path: str | Path) -> None:
    """Refuse to touch anything protected, $HOME itself, or shallow paths."""
    p = Path(path).expanduser()
    try:
        rp = p.resolve()
    except OSError:
        rp = p.absolute()
    if rp == HOME or rp == Path("/") or len(rp.parts) < 4:
        raise RuntimeError(f"refusing to touch risky path: {rp}")
    for prot in PROTECTED_PATHS:
        try:
            pr = prot.resolve()
        except OSError:
            pr = prot.absolute()
        if rp == pr or pr in rp.parents:
            raise RuntimeError(f"refusing to touch protected path: {rp}")


def du_bytes(path: Path) -> int:
    total = 0
    for dirpath, _dirs, files in os.walk(path, onerror=lambda e: None):
        for f in files:
            try:
                total += os.lstat(os.path.join(dirpath, f)).st_size
            except OSError:
                pass
    return total


def human(n: float) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if abs(n) < 1024 or unit == "T":
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1024
    return f"{n:.1f}T"


def meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, _, rest = line.partition(":")
            out[key] = int(rest.split()[0])
    except OSError:
        pass
    return out


def pids_using(path: Path) -> list[tuple[int, str]]:
    """Find processes whose cwd, cmdline or open fds live under `path`."""
    try:
        target = str(path.resolve())
    except OSError:
        target = str(path.absolute())
    hits: dict[int, str] = {}

    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        pid = int(proc.name)
        if pid == os.getpid():
            continue
        try:
            cwd = os.readlink(proc / "cwd")
            if cwd == target or cwd.startswith(target + os.sep):
                hits[pid] = f"cwd={cwd}"
                continue
        except OSError:
            pass
        try:
            cmd = (proc / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace")
            if target in cmd:
                hits[pid] = cmd[:140]
                continue
        except OSError:
            pass
        try:
            for fd in (proc / "fd").iterdir():
                try:
                    link = os.readlink(fd)
                except OSError:
                    continue
                if link.startswith(target + os.sep):
                    hits[pid] = f"open={link}"
                    break
        except OSError:
            pass
    return sorted(hits.items())


def ancestor_pids() -> set[int]:
    """PIDs of this process and everything above it."""
    chain: set[int] = set()
    pid = os.getpid()
    while pid > 1:
        chain.add(pid)
        try:
            status = Path(f"/proc/{pid}/status").read_text()
            m = re.search(r"^PPid:\s+(\d+)", status, re.M)
            if not m:
                break
            pid = int(m.group(1))
        except OSError:
            break
    return chain


def is_protected_process(pid: int) -> bool:
    """True for this session's ancestors and anything touching a protected path."""
    if pid in ancestor_pids():
        return True

    needles = []
    for prot in PROTECTED_PATHS:
        try:
            needles.append(str(prot.resolve()))
        except OSError:
            needles.append(str(prot.absolute()))

    def _touches(text: str) -> bool:
        return any(n in text for n in needles)

    try:
        cmd = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", "replace")
    except OSError:
        return True  # can't inspect -> leave it alone
    if _touches(cmd):
        return True
    if any(marker in cmd for marker in PROTECTED_CMDLINE_MARKERS):
        return True
    # the bot is a generic "node index.js": its cwd is what identifies it
    try:
        if _touches(os.readlink(f"/proc/{pid}/cwd")):
            return True
    except OSError:
        pass
    try:
        for fd in Path(f"/proc/{pid}/fd").iterdir():
            try:
                if _touches(os.readlink(fd)):
                    return True
            except OSError:
                continue
    except OSError:
        pass
    return False


def unit_exists(unit: str) -> bool:
    cp = run(["systemctl", "list-unit-files", unit])
    return cp.returncode == 0 and bool(cp.stdout.strip())


def svc_active(unit: str) -> bool:
    return run(["systemctl", "is-active", "--quiet", unit]).returncode == 0


def svc_enabled(unit: str) -> bool:
    return run(["systemctl", "is-enabled", "--quiet", unit]).returncode == 0


# --------------------------------------------------------------------------
# tasks
# --------------------------------------------------------------------------


def task_swap() -> None:
    """Reclaim stale swap, add zram, stop swapping so eagerly."""
    mem = meminfo()
    swap_kb = mem.get("SwapTotal", 0)
    avail_kb = mem.get("MemAvailable", 0)
    swappiness = run(["cat", "/proc/sys/vm/swappiness"]).stdout.strip()
    log(f"  swap: {swap_kb / 1048576:.1f} GB total, "
        f"{(swap_kb - mem.get('SwapFree', 0)) / 1048576:.1f} GB used | "
        f"available RAM: {avail_kb / 1048576:.1f} GB | swappiness={swappiness}")

    if swap_kb and avail_kb < swap_kb * 1.2:
        log("  SKIP reclaim: not enough free RAM to safely swap off")
        MANUAL.append("Re-run the swap task once memory pressure drops.")
    elif swap_kb:
        do(["swapoff", "-a"], root=True)
        do(["swapon", "-a"], root=True)
        if not DRY:
            new = meminfo()
            log("  after: swap used "
                f"{(new.get('SwapTotal', 0) - new.get('SwapFree', 0)) / 1048576:.1f} GB")
        else:
            log("  [dry-run] swap would be reclaimed above")

    # zram
    svc = "zramswap.service"
    if not unit_exists(svc):
        log("  zram: zram-tools not installed")
        do(["apt-get", "install", "-y", "zram-tools"], root=True)
    if unit_exists(svc) or DRY:
        cfg = Path("/etc/default/zramswap")
        current = cfg.read_text(errors="replace") if cfg.exists() else ""
        if "ALGO=zstd" not in current:
            write_root(cfg, "ALGO=zstd\nPERCENT=25\n")
            if not DRY:
                do(["systemctl", "enable", "zramswap"], root=True, quiet=True)
                do(["systemctl", "restart", "zramswap"], root=True)
    elif not DRY:
        MANUAL.append("zram-tools installed but zramswap.service is missing; "
                      "enable it manually.")

    sysctl_file = Path("/etc/sysctl.d/99-swap.conf")
    want = "vm.swappiness=20\nvm.vfs_cache_pressure=50\n"
    if not sysctl_file.exists() or sysctl_file.read_text(errors="replace") != want:
        write_root(sysctl_file, want)
        do(["sysctl", "--system"], root=True, quiet=True)
    if not DRY:
        log(f"  swappiness now: {run(['cat', '/proc/sys/vm/swappiness']).stdout.strip()}")


def task_boot() -> None:
    """Trim slow / unnecessary units from boot."""
    targets: list[tuple[str, bool, str]] = []

    targets.append(("NetworkManager-wait-online.service", True,
                    "blocks docker on network-online.target (5.9s)"))
    if not glob.glob("/sys/class/wwan*"):
        targets.append(("ModemManager.service", True,
                        "no WWAN device found (5.8s)"))

    containers = run(["docker", "ps", "-q"]).stdout.strip()
    if containers:
        log("  docker containers are running -> leaving docker/containerd alone")
    else:
        targets.append(("docker.service", False, "no running containers"))
        targets.append(("containerd.service", False, "only needed by docker"))

    targets.append(("fwupd.service", True,
                    "fwupd-refresh.timer still handles firmware"))

    for unit, stop_now, why in targets:
        if not unit_exists(unit):
            continue
        if not svc_enabled(unit):
            log(f"  {unit}: already disabled")
            continue
        log(f"  {unit}: {why}")
        cmd = ["systemctl", "disable"]
        if stop_now:
            cmd.append("--now")
        cmd.append(unit)
        do(cmd, root=True)

    dropin = Path("/etc/systemd/system/plocate-updatedb.timer.d/override.conf")
    if not dropin.exists():
        do(["mkdir", "-p", str(dropin.parent)], root=True, quiet=True)
        write_root(dropin, "[Timer]\nPersistent=false\n")
        do(["systemctl", "daemon-reload"], root=True, quiet=True)
        log("  plocate-updatedb: no longer replays a missed job at boot (7.9s)")
    REBOOT_NEEDED.append("Boot-time service changes take effect after reboot.")


def task_grub() -> None:
    """GRUB_TIMEOUT 10 -> 2 (the loader stage is 10.2s of a 30.7s boot)."""
    p = Path("/etc/default/grub")
    if not p.exists():
        log("  /etc/default/grub not found, skipping")
        return
    try:
        text = p.read_text(errors="replace")  # world-readable, no sudo needed
    except OSError as exc:
        log(f"  cannot read /etc/default/grub ({exc}), skipping")
        return
    m = re.search(r"^GRUB_TIMEOUT=(\d+)$", text, re.M)
    current = m.group(1) if m else "?"
    log(f"  GRUB_TIMEOUT currently {current}")
    if current in ("0", "1", "2", "3"):
        log("  already short enough")
        return
    new = re.sub(r"^GRUB_TIMEOUT=.*$", "GRUB_TIMEOUT=2", text, count=1,
                 flags=re.M)
    if "GRUB_TIMEOUT_STYLE" not in new:
        new += "GRUB_TIMEOUT_STYLE=hidden\n"
    backup_root(p)
    write_root(p, new)
    do(["update-grub"], root=True)
    REBOOT_NEEDED.append("GRUB timeout 10s -> 2s (saves ~8s per boot).")


AUTOSTART_DISABLE = [
    ("nvidia-prime", "no NVIDIA GPU (Intel HD 520 only)"),
    ("polkit-mate-authentication-agent-1", "MATE agent, you run Cinnamon"),
    ("onboard-autostart", "on-screen keyboard"),
    ("orca-autostart", "screen reader"),
    ("warpinator-autostart", "file sharing, not in use"),
    ("geoclue-demo-agent", "location demo agent"),
    ("org.gnome.Evolution-alarm-notify", "Evolution alarms"),
    ("im-launch", "input method launcher"),
    ("mintwelcome", "first-run welcome window"),
    ("mintreport", "crash report helper"),
]


def task_autostart() -> None:
    """Hide ~10 useless XDG autostart entries for this user only."""
    dest = HOME / ".config/autostart"
    if not DRY:
        dest.mkdir(parents=True, exist_ok=True)
    hidden = 0
    for name, why in AUTOSTART_DISABLE:
        f = dest / f"{name}.desktop"
        if f.exists() and "Hidden=true" in f.read_text(errors="replace"):
            log(f"  {name}: already hidden")
            continue
        log(f"  {name}: {why}")
        if not DRY:
            f.write_text("[Desktop Entry]\nType=Application\n"
                         f"Name={name}\nHidden=true\n")
        hidden += 1
    log(f"  {hidden} entries " + ("would be hidden" if DRY else "hidden")
        + " (per-user, reversible by deleting files)")
    MANUAL.append("Autostart changes apply at next login.")


def task_docker() -> None:
    """Reclaim ~5 GB of docker build cache and dangling images."""
    if not shutil.which("docker"):
        log("  docker not installed")
        return
    info = run(["docker", "info"], timeout=30)
    if info.returncode != 0:
        log("  docker daemon not reachable as this user, skipping")
        MANUAL.append("Docker cleanup: run 'docker system df' manually (needs docker group/root).")
        return
    log("  before:")
    for line in run(["docker", "system", "df"], timeout=30).stdout.splitlines():
        log(f"    {line}")
    do(["docker", "builder", "prune", "-f"], timeout=600)
    do(["docker", "image", "prune", "-f"], timeout=600)
    if INCLUDE_RISKY:
        do(["docker", "image", "prune", "-a", "-f"], timeout=600)
        do(["docker", "container", "prune", "-f"], timeout=300)
    else:
        log("  tagged images (3.9 GB) and stopped containers left alone:")
        log("    re-run with --include-risky to remove them")
    log("  after:")
    for line in run(["docker", "system", "df"], timeout=30).stdout.splitlines():
        log(f"    {line}")


def task_apt() -> None:
    do(["apt-get", "clean"], root=True)
    log(f"  /var/cache/apt/archives now: "
        f"{human(du_bytes(Path('/var/cache/apt/archives')))}")


def task_journal() -> None:
    before = run(["journalctl", "--disk-usage"], root=True).stdout.strip()
    log(f"  before: {before}")
    do(["journalctl", "--vacuum-size=200M"], root=True)
    after = run(["journalctl", "--disk-usage"], root=True).stdout.strip()
    log(f"  after:  {after}")


def task_coredumps() -> None:
    listing = run(["coredumpctl", "list", "--no-pager"], root=True).stdout
    count = max(0, len(listing.strip().splitlines()) - 1)
    log(f"  {count} coredump(s) on disk")
    if count:
        do(["coredumpctl", "clean"], root=True)


def task_caches() -> None:
    """Clear regenerable caches. Skips anything in use or protected."""
    targets = [HOME / ".cache/codex-runtimes"]
    brave_running = run(["pgrep", "-x", "brave"]).returncode == 0
    if brave_running:
        log("  Brave is running -> leaving ~/.cache/BraveSoftware (1.5 GB)")
        MANUAL.append("Close Brave, then delete ~/.cache/BraveSoftware to reclaim 1.5 GB.")
    else:
        targets.append(HOME / ".cache/BraveSoftware")

    for t in targets:
        if not t.exists():
            continue
        try:
            guard(t)
        except RuntimeError as exc:
            log(f"  {exc}")
            continue
        users = pids_using(t)
        if users:
            log(f"  {t.name}: in use by {len(users)} process(es), skipping")
            continue
        size = du_bytes(t)
        log(f"  {t}: {human(size)}")
        if not DRY:
            shutil.rmtree(t, ignore_errors=True)


def task_flatpak() -> None:
    if not shutil.which("flatpak"):
        log("  flatpak not installed")
        return
    log("  repairing system flatpak metadata (fixes appstream errors)")
    do(["flatpak", "repair", "--system"], root=True, timeout=900)


def task_casper() -> None:
    if not unit_exists("casper-md5check.service"):
        log("  unit not present")
        return
    if run(["systemctl", "is-failed", "--quiet", "casper-md5check.service"]).returncode == 0:
        log("  failed live-ISO leftover -> masking")
        do(["systemctl", "mask", "casper-md5check.service"], root=True)
    else:
        log("  not failed, nothing to do")


def task_bashrc() -> None:
    rc = HOME / ".bashrc"
    if not rc.exists():
        log("  no ~/.bashrc")
        return
    text = rc.read_text(errors="replace")
    if "# >>> optimize_mint >>>" in text:
        log("  history block already present")
        return
    block = (
        "\n# >>> optimize_mint >>>\n"
        "# larger, de-duplicated history (was HISTSIZE=1000)\n"
        "HISTSIZE=50000\n"
        "HISTFILESIZE=100000\n"
        "HISTCONTROL=ignoreboth:erasedups\n"
        "shopt -s histappend\n"
        "# <<< optimize_mint <<<\n"
    )
    if not DRY:
        shutil.copy2(rc, rc.with_suffix(".rc.bak"))
        with rc.open("a") as fh:
            fh.write(block)
        log("  appended history tuning to ~/.bashrc (backup: ~/.bashrc.rc.bak)")
    else:
        log("  [dry-run] would append HISTSIZE=50000 / HISTFILESIZE=100000 / "
            "HISTCONTROL=ignoreboth:erasedups to ~/.bashrc")


def task_power() -> None:
    """Better battery/AC behaviour. Uses ppd if present, else TLP."""
    ppd = shutil.which("powerprofilesctl")
    if ppd and svc_active("power-profiles-daemon"):
        log("  power-profiles-daemon is active -> using it instead of TLP")
        do(["powerprofilesctl", "set", "balanced"])
    else:
        if ppd and svc_enabled("power-profiles-daemon"):
            # TLP and ppd fight over the same knobs; ppd is inactive here
            log("  masking inactive power-profiles-daemon to avoid conflict")
            do(["systemctl", "mask", "power-profiles-daemon"], root=True)
        if not shutil.which("tlp"):
            do(["apt-get", "install", "-y", "tlp"], root=True)
        conf = Path("/etc/tlp.conf")
        if conf.exists():
            text = conf.read_text(errors="replace")
            if "CPU_ENERGY_PERF_POLICY_ON_AC=balance_performance" not in text:
                backup_root(conf)
                write_root(
                    conf,
                    text + "\n# added by optimize_mint.py\n"
                           "CPU_ENERGY_PERF_POLICY_ON_AC=balance_performance\n"
                           "CPU_ENERGY_PERF_POLICY_ON_BAT=power\n",
                )
        do(["systemctl", "enable", "--now", "tlp"], root=True)
        do(["tlp", "start"], root=True, quiet=True)

    # apply immediately without waiting for a reboot
    for pref in glob.glob(
            "/sys/devices/system/cpu/cpu*/cpufreq/energy_performance_preference"):
        write_root(pref, "balance_performance")


def task_opencode() -> None:
    """Vacuum the local DB and flag a duplicate server. Never kills this session."""
    db = HOME / ".local/share/opencode/opencode.db"
    if db.exists():
        before = db.stat().st_size
        log(f"  opencode.db: {human(before)}")
        if DRY:
            log("  [dry-run] sqlite VACUUM")
        else:
            try:
                conn = sqlite3.connect(f"file:{db}?mode=rw", uri=True, timeout=5)
                conn.execute("PRAGMA busy_timeout=5000")
                conn.execute("VACUUM")
                conn.close()
                log(f"  opencode.db after: {human(db.stat().st_size)}")
            except sqlite3.Error as exc:
                log(f"  skip VACUUM (db busy): {exc}")

    servers = []
    for pid_dir in Path("/proc").iterdir():
        if not pid_dir.name.isdigit():
            continue
        pid = int(pid_dir.name)
        try:
            cmd = (pid_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode(
                "utf-8", "replace")
        except OSError:
            continue
        if "opencode" in cmd and "serve" in cmd:
            servers.append((pid, cmd.strip()))

    log(f"  {len(servers)} opencode server process(es):")
    for pid, cmd in servers:
        tag = " <- this session" if pid in ancestor_pids() else ""
        log(f"    pid {pid}: {cmd[:110]}{tag}")

    extras = [p for p, _ in servers if p not in ancestor_pids()]
    if not extras:
        return
    if not INCLUDE_RISKY:
        log("  duplicate server left running (use --include-risky to stop it)")
        MANUAL.append("A second opencode server is listening on 0.0.0.0:4096.")
        return
    for pid in extras:
        if is_protected_process(pid):
            log(f"  pid {pid}: protected, not touching")
            continue
        log(f"  stopping duplicate opencode server pid {pid}")
        do(["kill", "-TERM", str(pid)])


def task_report() -> None:
    log("")
    log("Remaining items that need a human decision:")
    if not MANUAL:
        log("  (none)")
    for item in dict.fromkeys(MANUAL):
        log(f"  - {item}")
    log("")
    log("Not changed on purpose: whatsapp bot, Telegram downloads, cron jobs,")
    log("mysql/redis, cups/avahi/bluetooth, and the running Django dev server.")


# --------------------------------------------------------------------------
# registry / CLI
# --------------------------------------------------------------------------


@dataclass
class Task:
    key: str
    title: str
    fn: Callable[[], None]
    root: bool = False
    risky: bool = False
    default: bool = True


TASKS: list[Task] = [
    Task("swap", "Reclaim swap, add zram, tune swappiness", task_swap, root=True),
    Task("boot", "Disable slow/unneeded boot services", task_boot, root=True),
    Task("grub", "Cut GRUB timeout 10s -> 2s", task_grub, root=True),
    Task("autostart", "Hide ~10 useless autostart entries", task_autostart),
    Task("apt", "Clean apt package cache (~2.7 GB)", task_apt, root=True),
    Task("journal", "Cap systemd journal at 200 MB", task_journal, root=True),
    Task("coredumps", "Remove coredumps (Brave/opencode/sn-watcher)", task_coredumps, root=True),
    Task("caches", "Clear codex + Brave caches (~3.2 GB)", task_caches),
    Task("docker", "Prune docker build cache / dangling images", task_docker),
    Task("flatpak", "Repair flatpak metadata", task_flatpak, root=True),
    Task("casper", "Mask failed casper-md5check unit", task_casper, root=True),
    Task("bashrc", "Bigger, de-duplicated bash history", task_bashrc),
    Task("power", "TLP / power-profile tuning", task_power, root=True),
    Task("opencode", "Vacuum opencode DB, flag duplicate server", task_opencode),
    Task("report", "Summary of what's left", task_report),
]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Optimise this Linux Mint laptop. Read the header for what "
                    "is protected.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Tasks: " + ", ".join(t.key for t in TASKS))
    ap.add_argument("--dry-run", action="store_true",
                    help="print commands, change nothing")
    ap.add_argument("--yes", action="store_true",
                    help="non-interactive, run all selected tasks")
    ap.add_argument("--only", default="",
                    help="comma-separated task keys to run")
    ap.add_argument("--skip", default="",
                    help="comma-separated task keys to skip")
    ap.add_argument("--include-risky", action="store_true",
                    help="also prune tagged images/stopped containers and "
                         "stop duplicate opencode servers")
    ap.add_argument("--list", action="store_true", help="list tasks and exit")
    return ap.parse_args()


def main() -> int:
    global DRY, YES, INCLUDE_RISKY

    args = parse_args()
    DRY = args.dry_run
    YES = args.yes
    INCLUDE_RISKY = args.include_risky

    if args.list:
        for t in TASKS:
            flags = []
            if t.root:
                flags.append("root")
            if t.risky:
                flags.append("risky")
            print(f"  {t.key:<10} {t.title}"
                  + (f"  [{', '.join(flags)}]" if flags else ""))
        return 0

    if os.geteuid() == 0:
        log("Run this as your normal user, not root (it uses sudo itself).")
        return 2

    only = {s.strip() for s in args.only.split(",") if s.strip()}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    unknown = (only | skip) - {t.key for t in TASKS}
    if unknown:
        log(f"unknown task(s): {', '.join(sorted(unknown))}")
        return 2

    selected = [
        t for t in TASKS
        if t.key not in skip and (t.key in only if only else t.default)
    ]

    log("=" * 66)
    log(f"optimize_mint  {datetime.now():%Y-%m-%d %H:%M}"
        + ("   [DRY RUN]" if DRY else ""))
    log("=" * 66)
    log("Protected: whatsapp_bot, Downloads/Telegram, running dev servers,")
    log("           this opencode session, cron jobs, mysql, redis.")
    log("")

    if not DRY:
        log("Requesting sudo (one password prompt)...")
        if subprocess.run(["sudo", "-v"]).returncode != 0:
            log("sudo failed; aborting.")
            return 2

    run_all = YES
    ran: list[str] = []

    for t in selected:
        log("")
        log(f"-- {t.key}: {t.title} " + "-" * max(0, 40 - len(t.title)))
        if not run_all:
            try:
                ans = input(f"   run '{t.key}'? [y/N/a/q] ").strip().lower()
            except EOFError:
                ans = "n"
            if ans in ("q", "quit"):
                log("   stopped by user")
                break
            if ans in ("a", "all"):
                run_all = True
            elif ans not in ("y", "yes"):
                log("   skipped")
                continue
        try:
            t.fn()
            ran.append(t.key)
        except RuntimeError as exc:
            log(f"   ! blocked: {exc}")
        except Exception as exc:  # keep going on one bad task
            log(f"   ! {type(exc).__name__}: {exc}")

    log("")
    log("=" * 66)
    log(f"Done. Tasks run: {', '.join(ran) if ran else 'none'}")
    if DRY:
        log("This was a dry run. Re-run without --dry-run to apply.")
    if REBOOT_NEEDED:
        log("")
        log("Reboot to realise:")
        for item in REBOOT_NEEDED:
            log(f"  - {item}")
    log(f"Log: {LOG_PATH}")
    log("=" * 66)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\ninterrupted")
        sys.exit(130)
