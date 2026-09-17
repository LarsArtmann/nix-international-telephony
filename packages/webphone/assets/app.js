/* WebPhone: a SIP.js 0.21 WebRTC softphone served by this flake.
 *
 * Talks to FreeSWITCH mod_sofia over the WebSocket path proxied by nginx
 * (wss://<this-host>/sip) and therefore needs no extra browser plugins.
 *
 * Supports multiple concurrent calls with hold/switch, call transfer
 * (blind REFER and attended REFER-with-Replaces — FreeSWITCH performs the
 * actual transfer server-side), automatic transport reconnection with
 * re-registration, a DTMF keypad (application/dtmf-relay INFO), incoming-
 * call notifications with ringtone and tab flash, contacts with click-to-
 * dial, call history (local + server CDR), in-browser voicemail and an
 * ICE/media diagnostics panel — the last four via the phone API.
 */
(() => {
  "use strict";

  const config = window.PBX_CONFIG || {};
  const sipDomain = config.sipDomain || location.hostname;
  const wsPath = config.websocketPath || "/sip";
  const websocketUrl = `wss://${location.host}${wsPath}`;
  const iceServers = Array.isArray(config.iceServers) ? config.iceServers : [];
  const phoneApiEnabled = config.phoneApi === true;
  const sharedContacts = Array.isArray(config.contacts) ? config.contacts : [];
  const REMEMBER_KEY = "pbx-extension";
  const HISTORY_KEY = "pbx-history";
  const HISTORY_MAX = 20;
  const CONTACTS_KEY = "pbx-contacts";
  const CONTACTS_MAX = 50;
  const LANG_KEY = "pbx-lang";

  // --- i18n (de/en) -----------------------------------------------------------
  // Static strings carry data-i18n attributes applied by applyI18n();
  // dynamic strings (status pill, call cards, errors) go through t().
  // The event log stays English on purpose — it is operator-facing
  // diagnostics and the runbook greps these phrasings.
  const I18N = {
    en: {
      regState: "Registration state",
      signin: "Sign in to your extension",
      extension: "Extension",
      password: "Password",
      remember: "remember extension on this device (never the password)",
      connect: "Connect",
      signedInAs: "signed in as",
      signOut: "sign out",
      signOutTitle: "Unregister and sign out",
      dialPlaceholder: "Number, e.g. 1001, 2000, +441632960961",
      call: "Call",
      hold: "Hold",
      resume: "Resume",
      focus: "Focus",
      mute: "Mute",
      unmute: "Unmute",
      end: "End call",
      incoming: "Incoming call from",
      accept: "Accept",
      reject: "Reject",
      recentCalls: "Recent calls",
      eventLog: "Event log",
      offline: "offline",
      registered: "registered",
      regRejected: "registration rejected — check credentials",
      onHold: "on hold",
      inCall: "in call",
      calling: "calling…",
      ringing: "ringing…",
      ending: "ending…",
      transfer: "Transfer",
      transferPrompt: "transfer to",
      transferBlind: "Blind",
      transferAttended: "Attended",
      transferring: "transferring…",
      transferFailed: (detail) => `transfer failed: ${detail}`,
      transferNoPartner: "no second established call for an attended transfer",
      transferComplete: "transfer completed by the network",
      reconnectPreserved: (n) => `re-registered; ${n} call(s) preserved`,
      contacts: "Contacts",
      contactShared: "shared",
      contactSave: "save",
      contactRemove: "remove",
      voicemail: "Voicemail",
      vmRefresh: "Refresh",
      vmEmpty: "no messages",
      vmDelete: "delete",
      vmAuthFailed: "voicemail needs the operator API (not reachable)",
      vmNewCount: (n) => `${n} new`,
      connectionQuality: "Connection quality",
      iceNoMedia:
        "no media path yet — if the other side stays silent, TURN (ports 3478/5349 UDP) may be blocked",
      iceRelay:
        "media relays through TURN (expected behind strict NAT; adds a little latency)",
      iceSrflx: "direct path via STUN (router hole-punched)",
      iceHost: "direct local-network path",
      iceLoss: (lost) =>
        `${lost} packets lost on receive — network congestion?`,
      iceFailed: "connection failed — media blocked between the networks",
      reconnecting: (delay, attempt) =>
        `reconnecting in ${delay}s (try ${attempt})`,
      loginError: (message) =>
        `Could not connect: ${message}. Check extension/password and that your browser trusts the server certificate.`,
      callFailed: (detail) => `call failed: ${detail}`,
      callEnded: (dur) => `call ended · ${dur}`,
      missedCall: (from) => `missed call from ${from}`,
      noActiveCall: "no active call",
      notConnected: "not connected — sign in first",
      audioBlocked:
        "browser blocked audio playback — click the page to enable sound",
      rejectedSecond: "second incoming call rejected (one call at a time)",
    },
    de: {
      regState: "Registrierungsstatus",
      signin: "Anmeldung an Ihrer Nebenstelle",
      extension: "Nebenstelle",
      password: "Passwort",
      remember: "Nebenstelle auf diesem Gerät merken (niemals das Passwort)",
      connect: "Verbinden",
      signedInAs: "angemeldet als",
      signOut: "abmelden",
      signOutTitle: "Abmelden und Registrierung lösen",
      dialPlaceholder: "Nummer, z. B. 1001, 2000, +441632960961",
      call: "Anrufen",
      hold: "Halten",
      resume: "Fortsetzen",
      focus: "Aktivieren",
      mute: "Stumm",
      unmute: "Stumm aus",
      end: "Auflegen",
      incoming: "Eingehender Anruf von",
      accept: "Annehmen",
      reject: "Ablehnen",
      recentCalls: "Letzte Anrufe",
      eventLog: "Ereignisprotokoll",
      offline: "offline",
      registered: "registriert",
      regRejected: "Registrierung abgelehnt — Zugangsdaten prüfen",
      onHold: "gehalten",
      inCall: "im Gespräch",
      calling: "wird gewählt…",
      ringing: "klingelt…",
      ending: "wird beendet…",
      transfer: "Weiterleiten",
      transferPrompt: "weiterleiten an",
      transferBlind: "sofort",
      transferAttended: "Rückfrage",
      transferring: "wird weitergeleitet…",
      transferFailed: (detail) => `Weiterleitung fehlgeschlagen: ${detail}`,
      transferNoPartner:
        "kein zweiter bestehender Anruf für Rückfrage-Weiterleitung",
      transferComplete: "Weiterleitung vom Netz bestätigt",
      reconnectPreserved: (n) => `neu registriert; ${n} Gespräch(e) erhalten`,
      contacts: "Kontakte",
      contactShared: "gemeinsam",
      contactSave: "merken",
      contactRemove: "entfernen",
      voicemail: "Mailbox",
      vmRefresh: "Aktualisieren",
      vmEmpty: "keine Nachrichten",
      vmDelete: "löschen",
      vmAuthFailed: "Mailbox-API nicht erreichbar",
      vmNewCount: (n) => `${n} neu`,
      connectionQuality: "Verbindungsqualität",
      iceNoMedia:
        "noch kein Medienweg — falls die Gegenseite stumm bleibt, ist vermutlich TURN (UDP 3478/5349) blockiert",
      iceRelay:
        "Medien laufen über TURN (hinter strengem NAT normal; etwas mehr Laufzeit)",
      iceSrflx: "direkter Weg über STUN (Router-Lochbohrung)",
      iceHost: "direkter Weg im lokalen Netz",
      iceLoss: (lost) => `${lost} Pakete verloren — Netzüberlastung?`,
      iceFailed:
        "Verbindung fehlgeschlagen — Medien zwischen den Netzen blockiert",
      reconnecting: (delay, attempt) =>
        `Neuverbindung in ${delay}s (Versuch ${attempt})`,
      loginError: (message) =>
        `Verbindung fehlgeschlagen: ${message}. Prüfen Sie Nebenstelle/Passwort und ob Ihr Browser dem Serverzertifikat vertraut.`,
      callFailed: (detail) => `Anruf fehlgeschlagen: ${detail}`,
      callEnded: (dur) => `Anruf beendet · ${dur}`,
      missedCall: (from) => `verpasster Anruf von ${from}`,
      noActiveCall: "kein aktives Gespräch",
      notConnected: "nicht verbunden — bitte zuerst anmelden",
      audioBlocked:
        "Browser hat die Audiowiedergabe blockiert — Seite anklicken, um Ton zu aktivieren",
      rejectedSecond:
        "zweiter eingehender Anruf abgelehnt (ein Gespräch gleichzeitig)",
    },
  };

  let lang =
    localStorage.getItem(LANG_KEY) ||
    ((navigator.language || "en").toLowerCase().startsWith("de") ? "de" : "en");

  function t(key) {
    const table = I18N[lang] || I18N.en;
    return table[key] !== undefined ? table[key] : I18N.en[key];
  }

  function applyI18n() {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const value = t(el.dataset.i18n);
      if (typeof value === "string") el.textContent = value;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = t(el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
      el.title = t(el.dataset.i18nTitle);
    });
    if (els.lang) els.lang.value = lang;
  }

  const $ = (id) => document.getElementById(id);

  const els = {
    regStatus: $("reg-status"),
    lang: $("lang"),
    loginView: $("login-view"),
    loginForm: $("login-form"),
    loginError: $("login-error"),
    ext: $("ext"),
    pass: $("pass"),
    remember: $("remember"),
    phoneView: $("phone-view"),
    whoami: $("whoami-ext"),
    logout: $("logout"),
    dialForm: $("dial-form"),
    dest: $("dest"),
    calls: $("calls"),
    keypad: $("keypad"),
    history: $("history-list"),
    historyWrap: $("history-wrap"),
    incoming: $("incoming-call"),
    incomingFrom: $("incoming-from"),
    accept: $("accept-btn"),
    reject: $("reject-btn"),
    contactsWrap: $("contacts-wrap"),
    contactsList: $("contacts-list"),
    vmWrap: $("vm-wrap"),
    vmBadge: $("vm-badge"),
    vmList: $("vm-list"),
    vmRefresh: $("vm-refresh"),
    vmStatus: $("vm-status"),
    iceWrap: $("ice-wrap"),
    icePanel: $("ice-panel"),
    log: $("log"),
    toasts: $("toasts"),
    dialError: $("dial-error"),
    remoteAudio: $("remote-audio"),
  };

  let userAgent = null;
  let registerer = null;
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let stopping = false;
  // Credentials for rebuilding the connection after a hung reconnect
  // (kept in memory only; never persisted).
  let credentials = null;
  // True while a wedged user agent is being torn down and rebuilt;
  // suppresses the teardown's own disconnect/unregistered events.
  let resetting = false;

  // SIP.js 0.21's userAgent.reconnect() can hang forever after a
  // transport loss (observed by the browser E2E reconnect drill even
  // with the server reachable again). Bound every attempt; a hung one
  // gets a full rebuild instead of an eternal pill at "try N".
  const RECONNECT_ATTEMPT_TIMEOUT_MS = 5000;

  // id -> { session, target, held, muted, startedAt, timer, dom }
  const sessions = new Map();
  let focusedId = null;
  let incomingSession = null;

  // US ring cadence 2s on / 4s off at 440+480 Hz, generated locally.
  let ringbackCtx = null;
  let ringbackTimer = null;

  function log(message, level = "info") {
    const entry = document.createElement("li");
    entry.textContent = `${new Date().toISOString().slice(11, 19)} ${message}`;
    if (level !== "info") entry.dataset.level = level;
    els.log.prepend(entry);
    while (els.log.children.length > 100) els.log.lastChild.remove();
    // Devtools mirror: the on-page log is the operator trail, the browser
    // console is where a user actually looks when something misbehaves.
    console[level === "info" ? "info" : level]("webphone:", message);
  }

  // --- toasts: action feedback visible without opening the event log -------

  const TOAST_MAX = 4;
  const TOAST_MS = { info: 4000, ok: 4000, warn: 6000, error: 8000 };

  function announce(message, kind = "info") {
    log(message, kind === "ok" ? "info" : kind);
    const toast = document.createElement("div");
    toast.className = `toast toast-${kind}`;
    toast.textContent = message;
    toast.addEventListener("click", () => toast.remove());
    els.toasts.append(toast);
    while (els.toasts.children.length > TOAST_MAX) els.toasts.firstChild.remove();
    setTimeout(() => toast.remove(), TOAST_MS[kind] || TOAST_MS.info);
  }

  function setRegStatus(state, text) {
    els.regStatus.textContent = text;
    els.regStatus.className = `status ${state}`;
  }

  // --- ringback ------------------------------------------------------------

  function ringbackStart() {
    if (ringbackTimer) return;
    ringbackCtx = ringbackCtx || new AudioContext();
    const on = () => {
      const now = ringbackCtx.currentTime;
      [440, 480].forEach((freq) => {
        const osc = ringbackCtx.createOscillator();
        const gain = ringbackCtx.createGain();
        osc.frequency.value = freq;
        gain.gain.value = 0.06;
        osc.connect(gain).connect(ringbackCtx.destination);
        osc.start(now);
        osc.stop(now + 2);
      });
    };
    on();
    ringbackTimer = setInterval(on, 6000);
  }

  function ringbackStop() {
    if (ringbackTimer) clearInterval(ringbackTimer);
    ringbackTimer = null;
  }

  // --- incoming-call UX (notifications, ringtone, tab flash) -----------------

  // Ask once per device, from the login click (a user gesture — browsers
  // refuse permission prompts without one).
  function requestNotifications() {
    if (!("Notification" in window)) return;
    if (Notification.permission === "default") {
      Notification.requestPermission().then((state) => {
        log(`notifications ${state}`);
      });
    } else {
      log(`notifications ${Notification.permission}`);
    }
  }

  function notifyIncoming(from) {
    if (!("Notification" in window) || Notification.permission !== "granted")
      return;
    try {
      const n = new Notification(`☎ ${from}`, {
        body: `Incoming call on ${sipDomain}`,
        tag: "pbx-incoming",
      });
      n.addEventListener("click", () => window.focus());
    } catch (err) {
      log(`notification failed: ${err.message}`);
    }
  }

  // Distinct "internal ring" (faster cadence, single tone) so an incoming
  // call is audible even while a ringback plays for an outgoing leg.
  let ringToneCtx = null;
  let ringToneTimer = null;

  function ringToneStart() {
    if (ringToneTimer) return;
    ringToneCtx = ringToneCtx || new AudioContext();
    const burst = () => {
      const now = ringToneCtx.currentTime;
      [480, 960].forEach((freq) => {
        const osc = ringToneCtx.createOscillator();
        const gain = ringToneCtx.createGain();
        osc.frequency.value = freq;
        gain.gain.value = 0.05;
        osc.connect(gain).connect(ringToneCtx.destination);
        osc.start(now);
        osc.stop(now + 0.4);
      });
    };
    burst();
    ringToneTimer = setInterval(burst, 2000);
  }

  function ringToneStop() {
    if (ringToneTimer) clearInterval(ringToneTimer);
    ringToneTimer = null;
  }

  const originalTitle = document.title;
  let titleFlashTimer = null;

  function titleFlashStart() {
    if (titleFlashTimer) return;
    let on = false;
    titleFlashTimer = setInterval(() => {
      document.title = (on = !on) ? "☎ ☎ ☎" : originalTitle;
    }, 900);
  }

  function titleFlashStop() {
    if (!titleFlashTimer) return;
    clearInterval(titleFlashTimer);
    titleFlashTimer = null;
    document.title = originalTitle;
  }

  // --- call history ----------------------------------------------------------

  // Server-backed rows (CDR), fetched when the phone API is enabled; kept
  // separate from the local session history so reloads never lose either.
  let serverHistory = [];

  function readHistory() {
    try {
      const raw = JSON.parse(localStorage.getItem(HISTORY_KEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch {
      return [];
    }
  }

  function recordHistory(entry) {
    const list = [entry, ...readHistory()].slice(0, HISTORY_MAX);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
    renderHistory();
  }

  function authHeaderValue() {
    if (!credentials) return "";
    return `Basic ${btoa(`${credentials.extension}:${credentials.password}`)}`;
  }

  async function authedFetch(path, options = {}) {
    const headers = new Headers(options.headers || {});
    if (credentials) headers.set("Authorization", authHeaderValue());
    return fetch(path, { ...options, headers });
  }

  async function refreshServerHistory() {
    if (!phoneApiEnabled || !credentials) return;
    try {
      const res = await authedFetch("/phone-api/history?limit=20");
      if (!res.ok) return;
      const data = await res.json();
      serverHistory = Array.isArray(data.entries) ? data.entries : [];
      renderHistory();
    } catch (err) {
      log(`server history unavailable: ${err.message}`);
    }
  }

  function dialFromUi(number) {
    els.dest.value = number;
    els.dialForm.requestSubmit();
  }

  function makeHistoryRow({ dir, target, whenText, durText, number }) {
    const li = document.createElement("li");
    const dirEl = document.createElement("span");
    dirEl.className = "dir";
    dirEl.textContent = dir;
    const targetEl = document.createElement("strong");
    targetEl.textContent = target;
    const when = document.createElement("span");
    when.className = "when";
    when.textContent = whenText;
    const dur = document.createElement("span");
    dur.className = "when";
    dur.textContent = durText;
    li.append(dirEl, targetEl, when, dur);
    // Redial + save-as-contact: dialing gets fast, contacts stay local.
    const redial = document.createElement("button");
    redial.className = "ghost small redial";
    redial.textContent = "↻";
    redial.title = number;
    redial.addEventListener("click", () => dialFromUi(number));
    const save = document.createElement("button");
    save.className = "ghost small save";
    save.textContent = "☆";
    save.title = t("contactSave");
    save.addEventListener("click", () => {
      saveContact(number, number);
      renderContacts();
    });
    li.append(redial, save);
    return li;
  }

  function renderHistory() {
    const list = readHistory();
    els.historyWrap.hidden = list.length === 0 && serverHistory.length === 0;
    const localRows = list.map((entry) =>
      makeHistoryRow({
        dir: entry.dir === "in" ? "←" : "→",
        target: entry.target,
        whenText: new Date(entry.at).toLocaleString(),
        durText:
          entry.dur > 0
            ? `${Math.floor(entry.dur / 60)}:${String(entry.dur % 60).padStart(2, "0")}`
            : "—",
        number: entry.target,
      }),
    );
    const serverRows = serverHistory.map((row) =>
      makeHistoryRow({
        dir: row.context === "public" ? "←" : "→",
        target:
          row.context === "public"
            ? row.caller_id_number
            : row.destination_number,
        whenText: row.start || "—",
        durText:
          row.billsec > 0
            ? `${Math.floor(row.billsec / 60)}:${String(row.billsec % 60).padStart(2, "0")}`
            : "—",
        number:
          row.context === "public"
            ? row.caller_id_number
            : row.destination_number,
      }),
    );
    els.history.replaceChildren(...localRows, ...serverRows);
  }

  // --- contacts ---------------------------------------------------------------

  function readPersonalContacts() {
    try {
      const raw = JSON.parse(localStorage.getItem(CONTACTS_KEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch {
      return [];
    }
  }

  function saveContact(number, name) {
    const clean = String(number).replace(/[^\d+*#]/g, "");
    if (!clean) return;
    const list = [
      { name, number: clean },
      ...readPersonalContacts().filter((c) => c.number !== clean),
    ].slice(0, CONTACTS_MAX);
    localStorage.setItem(CONTACTS_KEY, JSON.stringify(list));
  }

  function removeContact(number) {
    const rest = readPersonalContacts().filter((c) => c.number !== number);
    localStorage.setItem(CONTACTS_KEY, JSON.stringify(rest));
  }

  function renderContacts() {
    if (!phoneApiEnabled && sharedContacts.length === 0) return;
    els.contactsWrap.hidden = false;
    const personal = readPersonalContacts();
    const mk = (contact, shared) => {
      const li = document.createElement("li");
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = contact.name;
      const number = document.createElement("span");
      number.className = "number";
      number.textContent = contact.number;
      const origin = document.createElement("span");
      origin.className = "origin";
      origin.textContent = shared ? t("contactShared") : "";
      const call = document.createElement("button");
      call.className = "ghost small call";
      call.textContent = "☎";
      call.addEventListener("click", () => dialFromUi(contact.number));
      li.append(name, number, origin);
      if (shared) {
        li.append(call);
      } else {
        const remove = document.createElement("button");
        remove.className = "ghost small";
        remove.textContent = "✕";
        remove.title = t("contactRemove");
        remove.addEventListener("click", () => {
          removeContact(contact.number);
          renderContacts();
        });
        li.append(call, remove);
      }
      return li;
    };
    els.contactsList.replaceChildren(
      ...sharedContacts.map((c) => mk(c, true)),
      ...personal.map((c) => mk(c, false)),
    );
  }

  // --- voicemail (phone API) ---------------------------------------------------

  let voicemailPoll = null;

  async function refreshVoicemail() {
    if (!phoneApiEnabled || !credentials) return;
    try {
      const headers = { Authorization: authHeaderValue() };
      const [summaryRes, listRes] = await Promise.all([
        fetch(`/phone-api/voicemail/${credentials.extension}/summary`, {
          headers,
        }),
        fetch(`/phone-api/voicemail/${credentials.extension}/messages`, {
          headers,
        }),
      ]);
      if (summaryRes.status === 401 || listRes.status === 401) {
        els.vmStatus.textContent = t("vmAuthFailed");
        return;
      }
      const summary = await summaryRes.json();
      const list = await listRes.json();
      const unread = Number.isFinite(summary.new) ? summary.new : 0;
      els.vmBadge.hidden = unread === 0;
      els.vmBadge.textContent = t("vmNewCount")(unread);
      els.vmWrap.hidden = false;
      els.vmStatus.textContent = "";
      const messages = Array.isArray(list.messages) ? list.messages : [];
      if (messages.length === 0) {
        els.vmList.replaceChildren(
          Object.assign(document.createElement("li"), {
            textContent: t("vmEmpty"),
          }),
        );
        return;
      }
      els.vmList.replaceChildren(
        ...messages.map((msg) => {
          const li = document.createElement("li");
          if (!msg.read) li.className = "unread";
          const caller = document.createElement("span");
          caller.className = "caller";
          caller.textContent = msg.cid_number || msg.cid_name || "?";
          const len = document.createElement("span");
          len.className = "len";
          len.textContent = `${msg.seconds}s`;
          const when = document.createElement("span");
          when.className = "when";
          when.textContent = new Date(msg.created * 1000).toLocaleString();
          const play = document.createElement("button");
          play.className = "ghost small";
          play.textContent = "▶";
          play.addEventListener("click", () => {
            new Audio(msg.audio_url)
              .play()
              .catch((err) => log(`playback: ${err.message}`));
          });
          const del = document.createElement("button");
          del.className = "ghost small";
          del.textContent = "🗑";
          del.title = t("vmDelete");
          del.addEventListener("click", async () => {
            try {
              const res = await authedFetch(
                `/phone-api/voicemail/${credentials.extension}/messages/${msg.uuid}`,
                { method: "DELETE" },
              );
              if (!res.ok) {
                log(`voicemail delete failed: HTTP ${res.status}`);
                return;
              }
              refreshVoicemail();
            } catch (err) {
              log(`voicemail delete failed: ${err.message}`);
            }
          });
          li.append(caller, len, when, play, del);
          return li;
        }),
      );
    } catch (err) {
      els.vmStatus.textContent = t("vmAuthFailed");
      log(`voicemail unavailable: ${err.message}`);
    }
  }

  function scheduleVoicemailRefresh() {
    if (!phoneApiEnabled) return;
    clearTimeout(voicemailPoll);
    voicemailPoll = setTimeout(refreshVoicemail, 1500);
  }

  // --- ICE/media diagnostics panel ---------------------------------------------

  function candidateTypeOf(stats, candidateId) {
    const candidate = stats.get(candidateId);
    return candidate ? `${candidate.candidateType || "?"}` : "?";
  }

  function iceHints(summary) {
    const hints = [];
    const pair = summary.selectedPair ? summary.selectedPairData : null;
    if (summary.localType === "relay" || summary.remoteType === "relay") {
      hints.push(t("iceRelay"));
    } else if (
      summary.localType === "srflx" ||
      summary.remoteType === "srflx"
    ) {
      hints.push(t("iceSrflx"));
    } else if (summary.localType === "host") {
      hints.push(t("iceHost"));
    } else if (
      (pair && pair.state === "failed") ||
      summary.iceState === "failed"
    ) {
      hints.push(t("iceFailed"));
    } else {
      hints.push(t("iceNoMedia"));
    }
    if (summary.packetsLost > 50) hints.push(t("iceLoss")(summary.packetsLost));
    return hints;
  }

  async function updateIcePanel() {
    if (!focusedId) return;
    const entry = sessions.get(focusedId);
    const pc =
      entry && entry.session.sessionDescriptionHandler
        ? entry.session.sessionDescriptionHandler.peerConnection
        : null;
    if (!pc) return;
    let stats;
    try {
      stats = await pc.getStats();
    } catch {
      return;
    }
    const summary = {
      iceState: pc.iceConnectionState,
      selectedPair: null,
      selectedPairData: null,
      localType: "",
      remoteType: "",
      rtt: null,
      packetsLost: 0,
      jitter: null,
      codec: "",
      bytesReceived: 0,
    };
    for (const stat of stats.values()) {
      if (stat.type === "transport" && stat.selectedCandidatePairId) {
        summary.selectedPair = stat.selectedCandidatePairId;
      }
      if (
        stat.type === "candidate-pair" &&
        (stat.selected || stat.nominated) &&
        stat.state === "succeeded"
      ) {
        summary.selectedPair = stat.id;
      }
      if (stat.type === "inbound-rtp" && stat.kind === "audio") {
        summary.packetsLost = stat.packetsLost || 0;
        summary.jitter = stat.jitter;
        summary.bytesReceived = stat.bytesReceived || 0;
      }
    }
    if (summary.selectedPair) {
      const pair = stats.get(summary.selectedPair);
      if (pair) {
        summary.selectedPairData = pair;
        summary.rtt = pair.currentRoundTripTime ?? null;
        summary.localType = candidateTypeOf(stats, pair.localCandidateId);
        summary.remoteType = candidateTypeOf(stats, pair.remoteCandidateId);
      }
    }
    for (const stat of stats.values()) {
      if (
        stat.type === "codec" &&
        stat.mimeType &&
        stat.mimeType.startsWith("audio")
      ) {
        summary.codec = stat.mimeType.replace("audio/", "");
        break;
      }
    }
    const lines = [
      `ice: ${summary.iceState}  path: ${summary.localType || "?"} → ${summary.remoteType || "?"}`,
      `codec: ${summary.codec || "?"}  rtt: ${summary.rtt != null ? `${Math.round(summary.rtt * 1000)} ms` : "—"}`,
      `received: ${summary.bytesReceived} B  lost: ${summary.packetsLost}  jitter: ${summary.jitter != null ? `${Math.round(summary.jitter * 1000)} ms` : "—"}`,
    ];
    const hints = iceHints(summary).map((hint) => `· ${hint}`);
    els.icePanel.replaceChildren(
      ...[...lines, ...hints].map((line) => {
        const div = document.createElement("div");
        if (line.startsWith("·")) div.className = "hintline";
        div.textContent = line;
        return div;
      }),
    );
  }

  let iceTimer = null;

  function startIcePanel() {
    if (iceTimer) return;
    updateIcePanel();
    iceTimer = setInterval(updateIcePanel, 2000);
  }

  function stopIcePanel() {
    if (!iceTimer) return;
    clearInterval(iceTimer);
    iceTimer = null;
    els.icePanel.replaceChildren();
  }

  // --- session helpers -------------------------------------------------------

  function outgoingCount() {
    let n = 0;
    sessions.forEach(({ session }) => {
      if (
        session instanceof SIP.Inviter &&
        session.state === SIP.SessionState.Establishing
      )
        n++;
    });
    return n;
  }

  function attachRemoteAudio(id) {
    const entry = sessions.get(id);
    if (!entry || !entry.session.sessionDescriptionHandler) return;
    const pc = entry.session.sessionDescriptionHandler.peerConnection;
    const remoteStream = new MediaStream();
    pc.getReceivers().forEach((receiver) => {
      if (receiver.track) remoteStream.addTrack(receiver.track);
    });
    els.remoteAudio.srcObject = remoteStream;
    els.remoteAudio
      .play()
      .catch((err) => log(`audio playback blocked: ${err.message}`));
  }

  function setTracks(entry, { recv, send }) {
    const sdh = entry.session.sessionDescriptionHandler;
    if (!sdh) return;
    if (recv !== undefined && sdh.enableReceiverTracks)
      sdh.enableReceiverTracks(recv);
    if (send !== undefined && sdh.enableSenderTracks)
      sdh.enableSenderTracks(send);
  }

  async function holdSession(id, hold) {
    const entry = sessions.get(id);
    if (!entry || entry.session.state !== SIP.SessionState.Established) return;
    if (entry.held === hold) return;
    entry.held = hold; // preemptive; undone if the re-INVITE fails
    try {
      await entry.session.invite();
      setTracks(entry, { recv: !hold, send: !hold && !entry.muted });
    } catch (err) {
      entry.held = !hold;
      log(`hold toggle failed: ${err.message}`);
    }
    renderCalls();
  }

  function focusSession(id) {
    if (!sessions.has(id)) return;
    focusedId = id;
    sessions.forEach((entry, otherId) => {
      if (otherId === id) {
        if (entry.held) holdSession(otherId, false);
      } else if (
        entry.session.state === SIP.SessionState.Established &&
        !entry.held
      ) {
        holdSession(otherId, true);
      }
    });
    attachRemoteAudio(id);
    renderCalls();
  }

  function teardownSession(id) {
    const entry = sessions.get(id);
    if (!entry) return;
    if (entry.timer) clearInterval(entry.timer);
    if (entry.dom) entry.dom.remove();
    sessions.delete(id);
    if (focusedId === id) {
      const next = sessions.keys().next();
      focusedId = next.done ? null : next.value;
      if (focusedId) attachRemoteAudio(focusedId);
    }
    renderCalls();
  }

  function durationLabel(startedAt) {
    const sec = Math.max(0, Math.floor((Date.now() - startedAt) / 1000));
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
  }

  function renderCalls() {
    sessions.forEach((entry, id) => {
      if (!entry.dom) return;
      const state = entry.session.state;
      const stateEl = entry.dom.querySelector(".call-state-text");
      if (state === SIP.SessionState.Established) {
        stateEl.textContent = entry.transferring
          ? t("transferring")
          : `${entry.held ? t("onHold") : t("inCall")} · ${durationLabel(entry.startedAt)}`;
      } else if (state === SIP.SessionState.Establishing) {
        stateEl.textContent = t("ringing");
      } else if (
        state === SIP.SessionState.Terminating ||
        state === SIP.SessionState.Terminated
      ) {
        stateEl.textContent = t("ending");
      }
      entry.dom.classList.toggle("focused", id === focusedId);
      const holdBtn = entry.dom.querySelector(".hold-btn");
      holdBtn.textContent = entry.held ? t("resume") : t("hold");
      const muteBtn = entry.dom.querySelector(".mute-btn");
      muteBtn.textContent = entry.muted ? t("unmute") : t("mute");
      const focusBtn = entry.dom.querySelector(".focus-btn");
      if (focusBtn) focusBtn.textContent = t("focus");
      const endBtn = entry.dom.querySelector(".hangup-btn");
      if (endBtn) endBtn.textContent = t("end");
    });
    const established =
      focusedId &&
      sessions.get(focusedId) &&
      sessions.get(focusedId).session.state === SIP.SessionState.Established;
    els.keypad.hidden = !established;
    els.iceWrap.hidden = sessions.size === 0;
    if (sessions.size > 0) startIcePanel();
    else stopIcePanel();
    if (outgoingCount() === 0) ringbackStop();
  }

  function addCallCard(id, target) {
    const card = document.createElement("div");
    card.className = "call-card";
    const head = document.createElement("div");
    head.className = "call-state";
    const targetEl = document.createElement("span");
    targetEl.className = "target";
    targetEl.textContent = target;
    const stateEl = document.createElement("span");
    stateEl.className = "call-state-text";
    stateEl.textContent = t("calling");
    head.append(stateEl, targetEl);
    const controls = document.createElement("div");
    controls.className = "controls";
    const mkBtn = (label, cls, onClick) => {
      const b = document.createElement("button");
      b.textContent = label;
      if (cls) b.className = cls;
      b.addEventListener("click", onClick);
      return b;
    };
    controls.append(
      mkBtn(t("focus"), "ghost focus-btn", () => focusSession(id)),
      mkBtn(t("mute"), "mute-btn", () => {
        const entry = sessions.get(id);
        if (!entry) return;
        entry.muted = !entry.muted;
        setTracks(entry, { send: !entry.held && !entry.muted });
        renderCalls();
      }),
      mkBtn(t("hold"), "hold-btn", () => {
        const entry = sessions.get(id);
        if (entry) holdSession(id, !entry.held);
      }),
      mkBtn(t("transfer"), "ghost transfer-btn", () =>
        toggleTransferRow(card, id),
      ),
      mkBtn(t("end"), "danger hangup-btn", () => hangup(id)),
    );
    card.append(head, controls);
    els.calls.append(card);
    return card;
  }

  // Transfer row: inline destination input with blind/attended actions.
  // FreeSWITCH executes the actual transfer server-side on the REFER
  // (source-verified: the REFERing party's partner leg is re-routed
  // through the dialplan on blind; the two existing calls are bridged on
  // attended via Replaces) — the browser only sends REFER and waits for
  // the NOTIFY sipfrag verdict.
  function toggleTransferRow(card, id) {
    const existing = card.querySelector(".transfer-row");
    if (existing) {
      existing.remove();
      return;
    }
    const row = document.createElement("div");
    row.className = "transfer-row";
    const input = document.createElement("input");
    input.inputMode = "tel";
    input.placeholder = t("transferPrompt");
    input.className = "transfer-dest";
    const blind = document.createElement("button");
    blind.className = "ghost small";
    blind.textContent = t("transferBlind");
    const attended = document.createElement("button");
    attended.className = "ghost small";
    attended.textContent = t("transferAttended");
    blind.addEventListener("click", () => {
      const dest = input.value.trim();
      if (dest) blindTransfer(id, dest);
    });
    attended.addEventListener("click", () => attendedTransfer(id));
    row.append(input, blind, attended);
    card.append(row);
    input.focus();
  }

  function referOnNotify(notification) {
    const body = (notification.request && notification.request.body) || "";
    const status = body.match(/^SIP\/2\.0 (\d{3})/m);
    notification.accept().catch(() => {});
    if (status && /^2/.test(status[1])) {
      log(t("transferComplete"));
      return;
    }
    log(t("transferFailed")(status ? status[1] : "no final NOTIFY"));
  }

  async function blindTransfer(id, destination) {
    const entry = sessions.get(id);
    if (!entry || entry.session.state !== SIP.SessionState.Established) return;
    const target = destination.replace(/[^\d+*#]/g, "");
    const uri = SIP.UserAgent.makeURI(`sip:${target}@${sipDomain}`);
    if (!uri) {
      log(t("transferFailed")("bad destination"));
      return;
    }
    entry.transferring = true;
    renderCalls();
    try {
      await entry.session.refer(uri, { onNotify: referOnNotify });
      log(`blind transfer ${entry.target} → ${target} sent`);
    } catch (err) {
      entry.transferring = false;
      log(t("transferFailed")(err.message));
      renderCalls();
    }
  }

  async function attendedTransfer(id) {
    const entry = sessions.get(id);
    if (!entry || entry.session.state !== SIP.SessionState.Established) return;
    // The other ESTABLISHED call is the consult leg; Replaces points at
    // its dialog so the network bridges the two far ends.
    let partner = null;
    sessions.forEach((other, otherId) => {
      if (
        otherId !== id &&
        other.session.state === SIP.SessionState.Established &&
        !other.transferring
      )
        partner = other;
    });
    if (!partner) {
      log(t("transferNoPartner"));
      return;
    }
    entry.transferring = true;
    renderCalls();
    try {
      await entry.session.refer(partner.session, { onNotify: referOnNotify });
      log(`attended transfer ${entry.target} ↔ ${partner.target} sent`);
    } catch (err) {
      entry.transferring = false;
      log(t("transferFailed")(err.message));
      renderCalls();
    }
  }

  // Diagnostic handle: the E2E suite reads getStats() from these to
  // prove real media flows (bytes on the wire), not just signaling.
  window.__pcs = window.__pcs || new Map();

  function bindSession(newSession, target) {
    newSession.stateChange.addListener((state) => {
      if (state === SIP.SessionState.Established) {
        const pc =
          newSession.sessionDescriptionHandler &&
          newSession.sessionDescriptionHandler.peerConnection;
        if (pc) window.__pcs.set(newSession.id, pc);
      }
    });
    const id = newSession.id;
    const entry = {
      session: newSession,
      target,
      held: false,
      muted: false,
      startedAt: Date.now(),
      timer: null,
      dom: addCallCard(id, target),
    };
    sessions.set(id, entry);
    focusedId = focusedId || id;
    if (newSession instanceof SIP.Inviter) ringbackStart();

    newSession.stateChange.addListener((state) => {
      const live = sessions.get(id);
      if (!live) return;
      log(`call ${target} ${state}`);
      if (state === SIP.SessionState.Established) {
        live.startedAt = Date.now();
        if (!live.timer) live.timer = setInterval(renderCalls, 1000);
        focusSession(id);
        // Call is no longer ringing: the incoming UX stops either way.
        titleFlashStop();
        ringToneStop();
      } else if (state === SIP.SessionState.Terminated) {
        const dur = Math.floor((Date.now() - live.startedAt) / 1000);
        recordHistory({
          dir: newSession instanceof SIP.Inviter ? "out" : "in",
          target,
          at: Date.now(),
          dur: dur > 0 ? dur : 0,
        });
        teardownSession(id);
        // A just-ended call may have left a voicemail deposit.
        scheduleVoicemailRefresh();
        refreshServerHistory();
      }
      renderCalls();
    });
    renderCalls();
  }

  async function hangup(id) {
    const entry = sessions.get(id);
    if (!entry) return;
    const current = entry.session;
    try {
      if (
        current instanceof SIP.Inviter &&
        current.state === SIP.SessionState.Initial
      ) {
        await current.cancel();
      } else if (current.state === SIP.SessionState.Established) {
        await current.bye();
      } else if (current instanceof SIP.Inviter) {
        await current.cancel();
      } else {
        await current.reject();
      }
    } catch (err) {
      log(`hangup: ${err.message}`);
      teardownSession(id);
    }
  }

  function sendDtmf(tone) {
    const entry = focusedId && sessions.get(focusedId);
    if (!entry || entry.session.state !== SIP.SessionState.Established) return;
    // application/dtmf-relay with "Signal=<d>" (equals): that is the
    // only form mod_sofia parses, and only with the profile flag
    // extended-info-parsing enabled (the generated profiles set it).
    // The colon form is 200-OK'd and silently dropped.
    const body = {
      contentDisposition: "render",
      contentType: "application/dtmf-relay",
      content: `Signal=${tone}\r\nDuration: 2000`,
    };
    entry.session
      .info({ requestOptions: { body } })
      .then(() => log(`dtmf ${tone}`))
      .catch((err) => log(`dtmf failed: ${err.message}`));
  }

  // --- connection --------------------------------------------------------------

  function scheduleReconnect() {
    if (stopping || reconnectTimer) return;
    reconnectAttempts += 1;
    const delay = Math.min(30, 2 ** reconnectAttempts);
    setRegStatus("status-offline", t("reconnecting")(delay, reconnectAttempts));
    log(`transport lost; reconnect try ${reconnectAttempts} in ${delay}s`);
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      attemptReconnect();
    }, delay * 1000);
  }

  function withTimeout(promise, ms, label) {
    let timer;
    return Promise.race([
      promise.then(
        (value) => {
          clearTimeout(timer);
          return value;
        },
        (err) => {
          clearTimeout(timer);
          throw err;
        },
      ),
      new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(label)), ms);
      }),
    ]);
  }

  // Tear the wedged agent down and build a fresh one (the page-reload
  // recovery path without losing the UI state).
  async function rebuildConnection(reason) {
    log(`reconnect watchdog: ${reason} — rebuilding connection`);
    resetting = true;
    const old = userAgent;
    userAgent = null;
    registerer = null;
    try {
      await withTimeout(
        old ? old.stop() : Promise.resolve(),
        3000,
        "stop timed out",
      );
    } catch (err) {
      log(`old agent stop: ${err.message}`);
    }
    try {
      await withTimeout(
        buildConnection(),
        RECONNECT_ATTEMPT_TIMEOUT_MS,
        "rebuild timed out",
      );
    } finally {
      resetting = false;
    }
  }

  async function attemptReconnect() {
    try {
      await withTimeout(
        (async () => {
          await userAgent.reconnect();
          await registerer.register();
        })(),
        RECONNECT_ATTEMPT_TIMEOUT_MS,
        "reconnect timed out",
      );
      reconnectAttempts = 0;
      log("transport reconnected; re-registered");
    } catch (err) {
      log(`reconnect failed: ${err.message}`);
      if (err.message.includes("timed out")) {
        // A hung attempt leaves the agent unusable — rebuild it.
        try {
          await rebuildConnection(err.message);
          reconnectAttempts = 0;
          return;
        } catch (resetErr) {
          log(`rebuild failed: ${resetErr.message}`);
        }
      }
      scheduleReconnect();
    }
  }

  async function connect(extension, password) {
    stopping = false;
    reconnectAttempts = 0;
    credentials = { extension, password };
    await buildConnection();
  }

  async function buildConnection() {
    const { extension, password } = credentials;
    const uri = SIP.UserAgent.makeURI(`sip:${extension}@${sipDomain}`);
    if (!uri) throw new Error(`invalid extension "${extension}"`);

    userAgent = new SIP.UserAgent({
      uri,
      authorizationUsername: extension,
      authorizationPassword: password,
      transportOptions: { server: websocketUrl },
      sessionDescriptionHandlerFactory:
        SIP.Web.defaultSessionDescriptionHandlerFactory(),
      sessionDescriptionHandlerFactoryOptions: {
        peerConnectionConfiguration: { iceServers },
      },
      logBuiltinEnabled: false,
      logLevel: "warn",
      delegate: {
        onDisconnect: (error) => {
          if (stopping || resetting) return;
          // Surface WHY the transport died — the pill is the first place
          // a user looks when audio goes quiet; "offline" alone hides
          // certificate/TLS vs network failures.
          const reason = error
            ? `offline: ${error.message || error}`
            : t("offline");
          setRegStatus("status-offline", reason);
          if (error) scheduleReconnect();
        },
        onInvite: (invitation) => {
          if (incomingSession) {
            invitation.reject();
            log("rejected second incoming call");
            return;
          }
          incomingSession = invitation;
          const from = (invitation.remoteIdentity &&
            invitation.remoteIdentity.uri) || {
            user: "unknown",
          };
          els.incomingFrom.textContent = from.user || "unknown";
          els.incoming.hidden = false;
          // Incoming-call UX: system notification, audible ring, tab flash.
          notifyIncoming(from.user || "unknown");
          ringToneStart();
          titleFlashStart();
          invitation.stateChange.addListener((state) => {
            if (state === SIP.SessionState.Terminated && !els.incoming.hidden) {
              els.incoming.hidden = true;
              incomingSession = null;
              ringToneStop();
              titleFlashStop();
            }
          });
          log(`incoming call from ${from.user}`);
        },
      },
    });

    await userAgent.start();

    registerer = new SIP.Registerer(userAgent);
    registerer.stateChange.addListener((state) => {
      log(`registration ${state}`);
      if (state === SIP.RegistererState.Registered) {
        const wasReconnecting = reconnectAttempts > 0;
        reconnectAttempts = 0;
        setRegStatus("status-registered", t("registered"));
        // Reconnect polish: after a transport recovery, say what the user
        // still has instead of silently resuming.
        if (wasReconnecting && sessions.size > 0) {
          log(t("reconnectPreserved")(sessions.size));
        }
      } else if (state === SIP.RegistererState.Unregistered) {
        // Deliberate logout or a rebuild's teardown sets its own pill;
        // anything else means the server rejected the REGISTER (wrong
        // credentials after a reconnect, account disabled) — say so
        // instead of "offline".
        if (!stopping && !resetting) {
          setRegStatus("status-offline", t("regRejected"));
        }
      } else {
        setRegStatus("status-offline", state.toLowerCase());
      }
    });
    await registerer.register();
  }

  function disconnect() {
    stopping = true;
    credentials = null;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = null;
    ringbackStop();
    [...sessions.keys()].forEach(teardownSession);
    focusedId = null;
  }

  // --- wiring ------------------------------------------------------------------

  if (localStorage.getItem(REMEMBER_KEY)) {
    els.ext.value = localStorage.getItem(REMEMBER_KEY);
    els.remember.checked = true;
  }
  renderHistory();

  if (els.lang) {
    els.lang.addEventListener("change", () => {
      lang = els.lang.value;
      localStorage.setItem(LANG_KEY, lang);
      applyI18n();
      renderCalls();
      log(`language switched to ${lang}`);
    });
  }
  applyI18n();

  els.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    els.loginError.hidden = true;
    // Permission prompts need a user gesture; the login click is the
    // natural one (a later denied state is shown in the log, not nagged).
    requestNotifications();
    try {
      const extension = els.ext.value.trim();
      await connect(extension, els.pass.value);
      if (els.remember.checked) localStorage.setItem(REMEMBER_KEY, extension);
      else localStorage.removeItem(REMEMBER_KEY);
      els.whoami.textContent = `${extension}@${sipDomain}`;
      els.loginView.hidden = true;
      els.phoneView.hidden = false;
      log(`connected via ${websocketUrl}`);
      // Phone-API backed panels: voicemail badge, server history, contacts.
      renderContacts();
      refreshVoicemail();
      refreshServerHistory();
    } catch (err) {
      els.loginError.textContent = t("loginError")(err.message);
      els.loginError.hidden = false;
      log(`connect failed: ${err.message}`);
    }
  });

  els.logout.addEventListener("click", async () => {
    try {
      [...sessions.values()].forEach(({ session }) => {
        session.bye().catch(() => {});
      });
      if (registerer) await registerer.unregister().catch(() => {});
      if (userAgent) await userAgent.stop().catch(() => {});
    } finally {
      disconnect();
      userAgent = null;
      registerer = null;
      ringToneStop();
      titleFlashStop();
      stopIcePanel();
      clearTimeout(voicemailPoll);
      setRegStatus("status-offline", t("offline"));
      els.phoneView.hidden = true;
      els.loginView.hidden = false;
    }
  });

  els.dialForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!userAgent) return;
    const raw = els.dest.value.trim();
    if (!raw) return;

    // Pasted numbers routinely carry invisible Unicode direction marks
    // (macOS/phone apps add them around telephone numbers) and formatting
    // (spaces, dashes, parentheses). makeURI rejects all of that, so strip
    // everything that is not dialable before building the SIP URI.
    const target = raw.replace(/[^\d+*#]/g, "");
    if (!target) {
      log(`nothing dialable in "${raw}" — enter digits, or + * #`);
      return;
    }

    const uri = SIP.UserAgent.makeURI(`sip:${target}@${sipDomain}`);
    if (!uri) {
      log(`invalid destination "${target}"`);
      return;
    }

    const inviter = new SIP.Inviter(userAgent, uri, {
      sessionDescriptionHandlerOptions: {
        constraints: { audio: true, video: false },
      },
    });
    bindSession(inviter, target);
    try {
      await inviter.invite();
    } catch (err) {
      log(`invite failed: ${err.message}`);
      teardownSession(inviter.id);
    }
  });

  els.accept.addEventListener("click", async () => {
    const invitation = incomingSession;
    if (!invitation) return;
    els.incoming.hidden = true;
    incomingSession = null;
    ringToneStop();
    titleFlashStop();
    bindSession(invitation, els.incomingFrom.textContent);
    try {
      await invitation.accept({
        sessionDescriptionHandlerOptions: {
          constraints: { audio: true, video: false },
        },
      });
    } catch (err) {
      log(`accept failed: ${err.message}`);
      teardownSession(invitation.id);
    }
  });

  els.reject.addEventListener("click", () => {
    if (incomingSession) incomingSession.reject();
    els.incoming.hidden = true;
    incomingSession = null;
    ringToneStop();
    titleFlashStop();
  });

  els.vmRefresh.addEventListener("click", () => refreshVoicemail());

  els.keypad.querySelectorAll("button[data-tone]").forEach((button) => {
    button.addEventListener("click", () => sendDtmf(button.dataset.tone));
  });

  log(`webphone loaded; sip domain ${sipDomain}`);
})();
