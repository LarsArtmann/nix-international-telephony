/* WebPhone: a minimal SIP.js 0.21 WebRTC softphone served by this flake.
 *
 * Talks to FreeSWITCH mod_sofia over the WebSocket path proxied by nginx
 * (wss://<this-host>/sip) and therefore needs no extra browser plugins.
 */
(() => {
  "use strict";

  const config = window.PBX_CONFIG || {};
  const sipDomain = config.sipDomain || location.hostname;
  const wsPath = config.websocketPath || "/sip";
  const websocketUrl = `wss://${location.host}${wsPath}`;
  const iceServers = Array.isArray(config.iceServers) ? config.iceServers : [];

  const $ = (id) => document.getElementById(id);

  const els = {
    regStatus: $("reg-status"),
    loginView: $("login-view"),
    loginForm: $("login-form"),
    loginError: $("login-error"),
    ext: $("ext"),
    pass: $("pass"),
    phoneView: $("phone-view"),
    whoami: $("whoami-ext"),
    logout: $("logout"),
    dialForm: $("dial-form"),
    dest: $("dest"),
    callControls: $("call-controls"),
    callState: $("call-state-text"),
    callTarget: $("call-target"),
    mute: $("mute-btn"),
    hangup: $("hangup-btn"),
    incoming: $("incoming-call"),
    incomingFrom: $("incoming-from"),
    accept: $("accept-btn"),
    reject: $("reject-btn"),
    log: $("log"),
    remoteAudio: $("remote-audio"),
  };

  let userAgent = null;
  let registerer = null;
  let session = null; // active Inviter or Invitation
  let incomingSession = null; // pending incoming Invitation
  let muted = false;

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

  function attachRemoteAudio() {
    const pc = session.sessionDescriptionHandler.peerConnection;
    const remoteStream = new MediaStream();
    pc.getReceivers().forEach((receiver) => {
      if (receiver.track) remoteStream.addTrack(receiver.track);
    });
    els.remoteAudio.srcObject = remoteStream;
    els.remoteAudio
      .play()
      .catch((err) => log(`audio playback blocked: ${err.message}`));
  }

  function setMuted(next) {
    muted = next;
    const pc =
      session &&
      session.sessionDescriptionHandler &&
      session.sessionDescriptionHandler.peerConnection;
    if (!pc) return;
    pc.getSenders().forEach((sender) => {
      if (sender.track) sender.track.enabled = !muted;
    });
    els.mute.textContent = muted ? "Unmute" : "Mute";
  }

  function leaveCallUi() {
    session = null;
    els.callControls.hidden = true;
    els.mute.textContent = "Mute";
    els.remoteAudio.srcObject = null;
  }

  function bindSession(newSession, target) {
    session = newSession;
    els.callControls.hidden = false;
    els.callState.textContent = "calling…";
    els.callTarget.textContent = target;

    newSession.stateChange.addListener((state) => {
      log(`session ${state}`);
      if (state === SIP.SessionState.Establishing) {
        els.callState.textContent = "ringing…";
      } else if (state === SIP.SessionState.Established) {
        els.callState.textContent = "in call";
        attachRemoteAudio();
      } else if (state === SIP.SessionState.Terminated) {
        if (session === newSession) leaveCallUi();
      }
    });
  }

  async function connect(extension, password) {
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
        onDisconnect: () => setRegStatus("status-offline", "offline"),
        onInvite: (invitation) => {
          if (session || incomingSession) {
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
        setRegStatus("status-registered", "registered");
      } else if (state !== SIP.RegistererState.Unregistered) {
        setRegStatus("status-offline", state.toLowerCase());
      }
    });
    await registerer.register();
  }

  els.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    els.loginError.hidden = true;
    try {
      await connect(els.ext.value.trim(), els.pass.value);
      els.whoami.textContent = `${els.ext.value.trim()}@${sipDomain}`;
      els.loginView.hidden = true;
      els.phoneView.hidden = false;
      log(`connected via ${websocketUrl}`);
    } catch (err) {
      els.loginError.textContent = `Could not connect: ${err.message}. Check extension/password and that your browser trusts the server certificate.`;
      els.loginError.hidden = false;
      log(`connect failed: ${err.message}`);
    }
  });

  els.logout.addEventListener("click", async () => {
    try {
      if (session) await session.bye().catch(() => {});
      if (registerer) await registerer.unregister().catch(() => {});
      if (userAgent) await userAgent.stop().catch(() => {});
    } finally {
      userAgent = null;
      registerer = null;
      session = null;
      setRegStatus("status-offline", "offline");
      els.phoneView.hidden = true;
      els.loginView.hidden = false;
    }
  });

  els.dialForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (session || incomingSession) return;
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
      leaveCallUi();
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
      leaveCallUi();
    }
  });

  els.reject.addEventListener("click", () => {
    if (incomingSession) incomingSession.reject();
    els.incoming.hidden = true;
    incomingSession = null;
  });

  els.hangup.addEventListener("click", async () => {
    const current = session;
    if (!current) return;
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
      leaveCallUi();
    }
  });

  els.mute.addEventListener("click", () => setMuted(!muted));

  log(`webphone loaded; sip domain ${sipDomain}`);
})();
