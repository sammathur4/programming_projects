# Whatsapp Bot using Node.js
Built using whatsapp-web.js and containerized using Docker.

## Features:
- Sends daily poll, pdf and remainders on a group.
- Welcomes users with a message specific to that group,  based on the group that user joins.
- Tag admins
- Admins can tag everyone present in the group (Members can not do this.)
- Add birthdays and update them
- View upcoming birthdays and birthdays of members in a specific month.
- Get birthday wishes at 12.00 AM
- Pin and unpin messages (admin only)
- Get Spotify song links directly in the chat
- **Mission 2026 habit check-in**: posts one ✅/❌ poll per habit every morning,
  tracks the group's votes, pushes them to the Mission 2026 backend and posts
  interim/final recaps with a per-person progress bar.

## Mission 2026 habit check-in

Talks to the Mission 2026 Django server (`mission2026/server`), so
check-ins land in the app and on the leaderboard without anyone installing it.

| Env var | What |
|---|---|
| `MISSION_GROUP_ID` | the group that gets the daily check-ins (`...@g.us`) |
| `MISSION_API_URL` | API root, e.g. `http://localhost:8000/api` |
| `MISSION_API_KEY` | optional — must match the server's `MISSION_API_KEY` |
| `MISSION_MORNING_CRON` | check-in start, default `0 20 * * *` (20:00) |
| `MISSION_INTERIM_CRON` | interim recap, default `0 22 * * *` (22:00) |
| `MISSION_FINAL_CRON` | final recap, default `55 23 * * *` (23:55) |
| `MISSION_REMINDER_MS` | silence before a reminder, default 5 min |
| `MISSION_PROCEED_MS` | silence before moving on, default 10 min |

Flow each day:

- **20:00** — habits are posted **one at a time** as plain messages. Answering
  the current one with *done* / *missed* (a reply, or just typing it) records
  the answer and sends the next habit.
- **no answer for 5 min** — one reminder quoting that habit. **10 min** — the
  chain moves on so it never stalls; late replies still count all day.
- **all day** — answers are pushed with `POST /api/mission/checkins/`.
- **22:00** — interim recap: every reporter's progress bar + who hasn't answered.
- **23:55** — final recap + the 30-day streak leaderboard.
- Answers are kept in `mission_state.json` (gitignored) and re-seeded from the
  server after a restart; a restart mid-evening resumes the chain where it was.

In-group commands (also work in DMs):

```
!mission                 your status for today
!mission done <habit>    mark a habit done  (e.g. !mission done 5L Water)
!mission missed <habit>  mark a habit missed
!mission habits          list today's habits and their keys
```

Habit keys are slugs of the habit name (`5L Water` → `5l_water`) and match the
backend's `habit_key()` exactly.

## Laptop control (owner only)

`helperFunctions/control.js` turns the bot into a remote for the machine it runs
on (X11 desktop — the bot inherits `DISPLAY` from its environment).

| Env var | What |
|---|---|
| `MISSION_OWNERS` | comma-separated WhatsApp ids/lids allowed to control the laptop |
| `MISSION_CONTROL_DRY_RUN` | `1` → log what would run, execute nothing |
| `MISSION_CONTROL_CWD` | the directory commands start in (default `$HOME`) |
| `MISSION_BROWSER` | browser binary for `!browser`/`!yt`/`!play` (default `brave-browser`) |
| `OPENCODE_BIN` | opencode binary (default `opencode`) |
| `OPENCODE_AGENT` | agent used for planning (default `planner`) |
| `OPENCODE_MODEL` | optional model override (default: the server's default) |
| `OPENCODE_TIMEOUT_MS` | per-call timeout (default `120000`) |
| `OPENCODE_FIX_ATTEMPTS` | how many times a failed command may be repaired (default `3`) |

To find your id, send any message in the group and read the bot log line
`[msg] from=… author=…` — the author part (`123…@lid`) is what goes in
`MISSION_OWNERS`.

```
!task <request>       ask opencode to do it — any wording you like
!cd [path]            change the working directory
!pwd                  show the working directory
!open <path|app|url>  file, folder, app name or link
!find <name>          locate files under $HOME
!ls [path]            list a directory
!play <file|url|search>   VLC for media, YouTube for a search
!hanuman              Hanuman Chalisa at 1.5x, looping
!others               rest of ~/Desktop/listen as a looping playlist
!yt [query]           search YouTube
!pause !resume !next !prev !stop
                          media transport (VLC via D-Bus, browsers via playerctl)
!vol <0-150|up|down|mute> system volume
!browser [query|url]  open/focus the browser (Brave)
!windows              list open windows
!focus <title>        raise a window
!close <title>        close a window
!key <combo>          send keys (xdotool), e.g. ctrl+t, super+d
!type <text>          type into the focused window
!mouse <x> <y> [button]   click at coordinates
!apps                 list launchable desktop apps
!screen               screenshot and send it
!lock                 lock the screen
!sys                  battery / memory / disk / uptime
!sh <command>         run a shell command
!control              this help
```

### `!task` — opencode does the understanding

`!task` is the free-form path. You say what you want in any words:

```
!task show me the 5 biggest folders in here
!task what's eating my disk space
!task find every .mp4 under my home
!task take a screenshot
```

opencode turns that into **one shell command** (or picks one of the bot's own
commands, e.g. `screen`, `play`, `vol`), the bot runs it in the current
working directory and sends back the real output.

**If the command fails, opencode works out the fix and the bot retries it.**
A wrong flag, a wrong path, a missing tool — opencode sees the error output,
repairs the command, and the bot runs the repaired one. You get the working
result, not an error dump. If nothing can be repaired, opencode explains what
went wrong and the bot still runs the closest working alternative.

### `!cd` — a working directory that sticks

```
!cd ~/Downloads          absolute
!cd project/src          relative to where you are now
!cd ..                   up one
!cd -                    back to the previous directory
!pwd                     where am I?
```

Every later command runs there: `!sh`, `!ls`, `!open`, `!task`, and the
commands opencode proposes. The directory is saved in `control_state.json`
(gitignored), so it survives a restart.

**Safety** (all enforced in code):

- **Owner only** — `!whoami` tells you whether your id is allowed. Everyone else
  gets "Not authorised", even in a DM.
- **No confirmation prompts** — the owner asked for the bot to just do the
  thing, so there is no "are you sure?" round trip. Every command runs
  immediately, including `!sh`.
- **Audit log** — every command, with sender + timestamp, appended to
  `control_audit.log` (gitignored).
- **Dry run** — `MISSION_CONTROL_DRY_RUN=1` prints intended commands instead of
  running them.
- **Failures are always reported** — a command that fails (missing binary,
  refused spawn, no audio sink, screenshot tool absent, WhatsApp rejecting the
  upload) replies with a `⚠️ …` message explaining what went wrong. A failed
  check-in write warns that it is queued, rather than claiming success.

### The `planner` agent

The bot runs the commands; opencode only plans them. To make sure opencode
never executes anything itself, it uses a `planner` agent with no shell. Put
this in `~/.config/opencode/opencode.json`:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "agent": {
    "planner": {
      "description": "Turns a request into a single shell command. It may read the filesystem to plan, but it never runs anything itself.",
      "mode": "primary",
      "tools": { "bash": false, "write": false, "edit": false, "patch": false, "task": false },
      "permission": { "bash": "deny", "edit": "deny", "task": "deny" }
    }
  }
}
```

If opencode was already running, `opencode service restart` makes it pick the
new agent up.

### Notes / limits

- VLC does not answer `playerctl` (it reports `Stopped` and the calls don't
  land), so transport goes through D-Bus `org.mpris.MediaPlayer2.vlc` directly
  and falls back to `playerctl` for browser players.
- The bot must be able to reach the running desktop session; if it is started
  from a service without `DISPLAY`, GUI commands will fail.
- `!screen` needs `gnome-screenshot` or ImageMagick's `import`.
- `!task` needs the `opencode` CLI on the bot's `PATH` and a working opencode
  service. Each call takes a few seconds — the bot says "🧠 Working on it…" if
  it takes longer than 8 seconds.

## How to run:
- Clone the repository, `npm i` followed by `npm start`
- Fill the environment variables with the format given in .env.example
- index.html will be available in localhost:3000

## Docker Image
- To make docker image `docker build -t <image-name>`
- To run `docker run -p 127.0.0.1:3000:3000 <image-name>` and index.html will be available in localhost:3000
