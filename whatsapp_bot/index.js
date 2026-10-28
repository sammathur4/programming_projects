const { Client, LocalAuth, Poll, RemoteAuth } = require("whatsapp-web.js");
const qrcode = require("qrcode");
const job = require("node-schedule");
const {
  sendDailyPoll,
  addBirthday,
  sendBirthdayWish,
  sendWelcomeMessage,
  listBirthdays,
  tagAdminsOnly,
  showBotHelp,
  getAllGroups,
  pinMessage,
  unpinMessage,
  searchSpotify,
  pongCommand,
  randomNumber,
  sendWaterReminder
} = require("./helperFunctions/helper");
const { SupabaseSessionStore } = require("./helperFunctions/supabase");
const mission = require("./helperFunctions/mission");
const control = require("./helperFunctions/control");

const express = require("express");
app = express();

// One broken WhatsApp-page call must never take the whole bot down
// (e.g. the getChatModel DataError that killed the !ping reply).
process.on("unhandledRejection", (reason) => {
  console.error("[fatal] unhandledRejection (kept alive):", reason && reason.message || reason);
});
process.on("uncaughtException", (err) => {
  console.error("[fatal] uncaughtException (kept alive):", err && err.message || err);
});

app.use(express.static("public"));

/** Endpoints that can post to the group must only be callable from this box. */
function isLoopback(req) {
  const ip = req.socket.remoteAddress || "";
  return ip === "127.0.0.1" || ip === "::1" || ip === "::ffff:127.0.0.1";
}

/**
 * Patch for whatsapp-web.js 1.34.7 on the current (2026) WhatsApp Web build:
 * WWebJS.getChatModel's lastMessage lookup ends up calling Msg.get(undefined)
 * (lastReceivedKey no longer serializes into a usable key), which throws an
 * IndexedDB DataError — this broke getChatById/getChats for every non-empty
 * chat ("r" in logs). The send path (getAsModel:false) is unaffected.
 *
 * We wrap the original: on failure we rebuild the same model without the
 * fragile lastMessage tail. Remove this once upstream fixes getChatModel.
 */
async function patchWWebJS(client) {
  if (!client.pupPage) return;
  try {
    const result = await client.pupPage.evaluate(async () => {
      if (window.__missionPatched || !window.WWebJS) return "skip";
      const original = window.WWebJS.getChatModel;
      window.WWebJS.getChatModel = async (chat, opts = {}) => {
        if (!chat) return null;
        try {
          return await original(chat, opts);
        } catch (e) {
          try {
            const model = chat.serialize();
            model.lastMessage = null;
            if (!opts.isChannel) {
              model.isGroup = !!chat.groupMetadata;
              if (chat.groupMetadata) {
                try {
                  const W = window
                    .require("WAWebWidFactory")
                    .createWid(chat.id._serialized);
                  const c = window.require("WAWebCollections");
                  const gm = c.GroupMetadata || c.WAWebGroupMetadataCollection;
                  await gm.update(W);
                  const meta = chat.groupMetadata.serialize();
                  try {
                    const { toPn } = window.require("WAWebLidMigrationUtils");
                    for (const p of meta.participants || []) {
                      const pn = toPn(p.id);
                      if (pn) p.id = pn;
                    }
                  } catch (_) {}
                  model.groupMetadata = meta;
                  model.isReadOnly = chat.groupMetadata.announce;
                } catch (_) {}
              }
              try {
                model.isMuted = chat.mute && chat.mute.expiration !== 0;
                model.formattedTitle = chat.formattedTitle;
              } catch (_) {}
            }
            delete model.msgs;
            delete model.msgUnsyncedButtonReplyMsgs;
            delete model.unsyncedButtonReplies;
            return model;
          } catch (e2) {
            return chat.serialize ? chat.serialize() : null;
          }
        }
      };
      window.__missionPatched = true;
      return "patched";
    });
    console.log("[patch] WWebJS.getChatModel guarded:", result);
  } catch (e) {
    console.error("[patch] failed:", e && e.message);
  }
}

let qrCodeImageUrl = null;
let clientReady = false;

const wwebVersion = "2.2412.54";

const client = new Client({
  authStrategy: new LocalAuth(),
  puppeteer:{
    headless:true,
    //executablePath: '/usr/bin/google-chrome',
    args: ['--no-sandbox', '--disable-setuid-sandbox'],

  }
});

client.initialize();

client.on("qr", (qr) => {
  // qrcode.generate(qr, { small: true });
  qrcode.toDataURL(qr, (err, url) => {
    console.log("QR UPDATES");
    qrCodeImageUrl = url;
  });
});

client.on("authenticated", () => {
  console.log("[lifecycle] authenticated — session stored");
});

client.on("loading_screen", (percent, message) => {
  console.log(`[lifecycle] loading ${percent}% ${message || ""}`);
});

client.on("auth_failure", () => {
  console.log("Authentication failed, Please login again.");
});
client.on("disconnected", () => {
  console.log("Disconnected");
});

client.on("ready", async () => {
  console.log("Client is ready.");
  clientReady = true;
  // getAllGroups(client);
  await patchWWebJS(client);
  // pick today's one-by-one check-in chain back up if we died mid-evening
  mission.resumeChain(client);

  const randomMins = randomNumber(0, 59);

  job.scheduleJob(`${randomMins} 10 * * *`, async () => {
    sendDailyPoll(client);
  });

  job.scheduleJob("0 0 * * *", async () => {
    sendBirthdayWish(client);
  });

  job.scheduleJob(`${randomMins} 5-13/4 * * *`, async () => {
    sendWaterReminder(client);
  });

  // 4 AM wake-up message
  job.scheduleJob("0 4 * * *", async () => {
    try {
      await client.sendMessage(mission.GROUP_ID, "Wake up!!!");
    } catch (e) {
      console.error("[wakeup] send failed:", e.message);
    }
  });

  // Mission 2026 habit check-in (see helperFunctions/mission.js)
  job.scheduleJob(mission.MORNING_CRON, () => mission.sendMorningCheckin(client));
  job.scheduleJob(mission.INTERIM_CRON, () => mission.sendRecap(client, { final: false }));
  job.scheduleJob(mission.FINAL_CRON, () => mission.sendRecap(client, { final: true }));
});

client.on("message", async (msg) => {
  // Log every chat we hear from — group messages carry the group id in
  // msg.from ("<id>@g.us"), which is what MISSION_GROUP_ID needs.
  console.log(`[msg] from=${msg.from} author=${msg.author || "-"} body=${JSON.stringify(String(msg.body || "").slice(0, 40))}`);
  // Mission check-in answers (reply-quote / "done" / "missed" while pending)
  mission.onMessage(client, msg);
  // Laptop control (owner-only) — stop here if it handled the message
  if (await control.handle(client, msg)) return;
  if (msg.body === "!help") {
    showBotHelp(client, msg);
  }
  if (msg.body === "!ping") {
    pongCommand(client, msg);
  }
  if (msg.body.startsWith("!birthday list")) {
    listBirthdays(msg, client);
  } else if (msg.body.startsWith("!birthday")) {
    addBirthday(msg, client);
  }
  // if (msg.body === "!everyone") {
  //   tagEveryone(msg);
  // }
  if (msg.body === "!admins") {
    tagAdminsOnly(msg);
  }
  if (msg.body === "!pin") {
    pinMessage(client,msg);
  }
  if (msg.body === "!unpin"){
    unpinMessage(client,msg);
  }
  if(msg.body.startsWith("!spotify")){
    searchSpotify(client,msg);
  }
  if (msg.body.startsWith("!mission")) {
    mission.handleCommand(client, msg);
  }
});

client.on("group_join", async (notification) => {
  sendWelcomeMessage(notification, client);
});

// Poll votes (habit check-ins) — see helperFunctions/mission.js
client.on("vote_update", async (vote) => {
  await mission.onVote(vote);
});

// Our own outgoing messages — used to learn the id of check-in items we
// sent (the sendMessage return path can come back empty on this WA build).
client.on("message_create", (msg) => {
  try {
    mission.onOwnMessage(msg);
  } catch (_) {}
});

app.get("/qr", (req, res) => {
  if (clientReady) {
    return res.json({ message: "Client is already authenticated" });
  }
  if (qrCodeImageUrl) {
    res.json({ qrCode: qrCodeImageUrl });
  } else {
    res.json({ message: "QR code not available. Please wait..." });
  }
});

app.get("/status", (req, res) => {
  res.json({ status: clientReady ? "ready" : "not ready" });
});

// Which groups the linked account is in — used to pick MISSION_GROUP_ID.
app.get("/groups", async (req, res) => {
  if (!clientReady) return res.status(503).json({ message: "client not ready" });
  try {
    const chats = await client.getChats();
    const groups = chats
      .filter((chat) => chat.isGroup)
      .map((chat) => ({ id: chat.id._serialized, name: chat.name || chat.formattedTitle || "" }));
    res.json({ groups });
  } catch (e) {
    res.status(500).json({ detail: e.message });
  }
});

// Manual triggers (loopback only) — "run the morning check-in now" / recap now.
app.post("/mission/morning", async (req, res) => {
  if (!isLoopback(req)) return res.status(403).json({ detail: "loopback only" });
  if (!clientReady) return res.status(503).json({ message: "client not ready" });
  await mission.sendMorningCheckin(client);
  res.json({ ok: true });
});

// Join a group from a chat.whatsapp.com invite (loopback only).
app.post("/invite/:code", async (req, res) => {
  if (!isLoopback(req)) return res.status(403).json({ detail: "loopback only" });
  if (!clientReady) return res.status(503).json({ message: "client not ready" });
  try {
    await client.acceptInvite(req.params.code);
    res.json({ ok: true, note: "joining — call /groups in a moment to get the id" });
  } catch (e) {
    res.status(400).json({ detail: e.message });
  }
});

app.post("/mission/recap", async (req, res) => {
  if (!isLoopback(req)) return res.status(403).json({ detail: "loopback only" });
  if (!clientReady) return res.status(503).json({ message: "client not ready" });
  await mission.sendRecap(client, { final: req.query.final === "1" });
  res.json({ ok: true });
});

app.listen(process.env.PORT || 3000, () => {
  console.log(`Server is running`);
});

const date = new Date();
const time = date.toLocaleTimeString();
console.log(`Current time: ${time}`);
