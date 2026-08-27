/* WebPhone: a SIP.js 0.21 WebRTC softphone served by this flake.
 *
 * Talks to FreeSWITCH mod_sofia over the WebSocket path proxied by nginx
 * (wss://<this-host>/sip) and therefore needs no extra browser plugins.
 *
 * Supports multiple concurrent calls with hold/switch, automatic
 * transport reconnection with re-registration, a DTMF keypad
 * (application/dtmf-relay INFO), call history and an in-call timer.
 */
(() => {
  "use strict";

  const config = window.PBX_CONFIG || {};
  const sipDomain = config.sipDomain || location.hostname;
  const wsPath = config.websocketPath || "/sip";
  const websocketUrl = `wss://${location.host}${wsPath}`;
  const iceServers = Array.isArray(config.iceServers) ? config.iceServers : [];
  const REMEMBER_KEY = "pbx-extension";
  const HISTORY_KEY = "pbx-history";
  const HISTORY_MAX = 20;
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
      reconnecting: (delay, attempt) =>
        `reconnecting in ${delay}s (try ${attempt})`,
      loginError: (message) =>
        `Could not connect: ${message}. Check extension/password and that your browser trusts the server certificate.`,
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
      reconnecting: (delay, attempt) =>
        `Neuverbindung in ${delay}s (Versuch ${attempt})`,
      loginError: (message) =>
        `Verbindung fehlgeschlagen: ${message}. Prüfen Sie Nebenstelle/Passwort und ob Ihr Browser dem Serverzertifikat vertraut.`,
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
    log: $("log"),
    remoteAudio: $("remote-audio"),
  };

  let userAgent = null;
  let registerer = null;
  let reconnectAttempts = 0;
  let reconnectTimer = null;
  let stopping = false;

  // id -> { session, target, held, muted, startedAt, timer, dom }
  const sessions = new Map();
  let focusedId = null;
  let incomingSession = null;

  // US ring cadence 2s on / 4s off at 440+480 Hz, generated locally.
  let ringbackCtx = null;
  let ringbackTimer = null;

  function log(message) {
    const entry = document.createElement("li");
    entry.textContent = `${new Date().toISOString().slice(11, 19)} ${message}`;
    els.log.prepend(entry);
    while (els.log.children.length > 100) els.log.lastChild.remove();
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

  // --- call history ----------------------------------------------------------

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

  function renderHistory() {
    const list = readHistory();
    els.historyWrap.hidden = list.length === 0;
    els.history.replaceChildren(
      ...list.map((entry) => {
        const li = document.createElement("li");
        const dir = document.createElement("span");
        dir.className = "dir";
        dir.textContent = entry.dir === "in" ? "←" : "→";
        const target = document.createElement("strong");
        target.textContent = entry.target;
        const when = document.createElement("span");
        when.className = "when";
        when.textContent = new Date(entry.at).toLocaleString();
        const dur = document.createElement("span");
        dur.className = "when";
        dur.textContent =
          entry.dur > 0
            ? `${Math.floor(entry.dur / 60)}:${String(entry.dur % 60).padStart(2, "0")}`
            : "—";
        li.append(dir, target, when, dur);
        return li;
      }),
    );
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
        stateEl.textContent = `${entry.held ? t("onHold") : t("inCall")} · ${durationLabel(entry.startedAt)}`;
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
      mkBtn(t("end"), "danger hangup-btn", () => hangup(id)),
    );
    card.append(head, controls);
    els.calls.append(card);
    return card;
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
      } else if (state === SIP.SessionState.Terminated) {
        const dur = Math.floor((Date.now() - live.startedAt) / 1000);
        recordHistory({
          dir: newSession instanceof SIP.Inviter ? "out" : "in",
          target,
          at: Date.now(),
          dur: dur > 0 ? dur : 0,
        });
        teardownSession(id);
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
    // application/dtmf-relay uses "Signal: <d>" (colon) — sofia ignores
    // the equals form silently (verified against mod_sofia parsing while
    // debugging the voicemail test client).
    const body = {
      contentDisposition: "render",
      contentType: "application/dtmf-relay",
      content: `Signal: ${tone}\r\nDuration: 2000`,
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
    reconnectTimer = setTimeout(async () => {
      reconnectTimer = null;
      try {
        await userAgent.reconnect();
        await registerer.register();
        reconnectAttempts = 0;
        log("transport reconnected; re-registered");
      } catch (err) {
        log(`reconnect failed: ${err.message}`);
        scheduleReconnect();
      }
    }, delay * 1000);
  }

  async function connect(extension, password) {
    stopping = false;
    reconnectAttempts = 0;
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
          if (stopping) return;
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
          invitation.stateChange.addListener((state) => {
            if (state === SIP.SessionState.Terminated && !els.incoming.hidden) {
              els.incoming.hidden = true;
              incomingSession = null;
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
        reconnectAttempts = 0;
        setRegStatus("status-registered", t("registered"));
      } else if (state === SIP.RegistererState.Unregistered) {
        // Deliberate logout sets its own pill; anything else means the
        // server rejected the REGISTER (wrong credentials after a
        // reconnect, account disabled) — say so instead of "offline".
        if (!stopping) {
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
    try {
      const extension = els.ext.value.trim();
      await connect(extension, els.pass.value);
      if (els.remember.checked) localStorage.setItem(REMEMBER_KEY, extension);
      else localStorage.removeItem(REMEMBER_KEY);
      els.whoami.textContent = `${extension}@${sipDomain}`;
      els.loginView.hidden = true;
      els.phoneView.hidden = false;
      log(`connected via ${websocketUrl}`);
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
      setRegStatus("status-offline", t("offline"));
      els.phoneView.hidden = true;
      els.loginView.hidden = false;
    }
  });

  els.dialForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!userAgent) return;
    const target = els.dest.value.trim();
    if (!target) return;

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
  });

  els.keypad.querySelectorAll("button[data-tone]").forEach((button) => {
    button.addEventListener("click", () => sendDtmf(button.dataset.tone));
  });

  log(`webphone loaded; sip domain ${sipDomain}`);
})();
