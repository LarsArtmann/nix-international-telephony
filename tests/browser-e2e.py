# Browser E2E: two headless chromium instances (fake media) register as
# extensions 1000 and 1001 through the nginx wss://pbx.test/sip proxy and
# complete a real 1000 -> 1001 WebRTC call (DTLS-SRTP), then hang up.
#
# Driven by Selenium; the NixOS testScript (tests/browser.nix) polls this
# script's stdout markers and asserts the call server-side via fs_cli.
# Every phase prints a marker BEFORE the slow part happens, so a stall in
# /tmp/e2e.log localises the failure (driver start, page load, login,
# registration, ring, answer) instead of manifesting as one opaque
# "<ext>-REGISTERED never appeared".
import os
import sys
import time
import traceback

from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CHROMEDRIVER = "@chromedriver@"
CHROMIUM = "@chromium@"
PASSWORDS = {"1000": "test-1000-x9y8z7", "1001": "test-1001-u6t5s4"}


def say(marker):
    print(marker, flush=True)


def make_driver(tag):
    options = ChromeOptions()
    options.binary_location = CHROMIUM
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    # Fake capture devices + auto-granted permissions: real WebRTC stacks,
    # no human, no hardware.
    options.add_argument("--use-fake-ui-for-media-stream")
    options.add_argument("--use-fake-device-for-media-stream")
    # The PBX vhost serves a runtime self-signed certificate.
    options.add_argument("--ignore-certificate-errors")
    options.set_capability("acceptInsecureCerts", True)
    # Capture console output (WebSocket failures, CSP violations) for the
    # failure dumps.
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    # Let the remote <audio> element play without a user gesture.
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--window-size=1280,900")
    # Verbose chromedriver log per browser: Selenium negotiations, session
    # errors and devtools messages land in /tmp/chromedriver-<tag>.log,
    # which the testScript dumps when a marker stalls.
    service = Service(
        executable_path=CHROMEDRIVER,
        service_args=["--verbose"],
        log_output=f"/tmp/chromedriver-{tag}.log",  # nosec B108 - test log
    )
    driver = webdriver.Chrome(service=service, options=options)
    # The silent-breakage gate: record every fetch's real status from the
    # page itself. A csrf 403 on POST /api/session leaves the call island
    # fully working (registration is browser-side) while every tab stays
    # dead — exactly the 2026-09-19 prod outage the old markers could not
    # see. CDP keeps the recorder across reloads (login rotation and the
    # reconnect drill both reload); the island itself is untouched.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument", {"source": FETCH_RECORDER_JS}
    )
    say(f"DRIVER-STARTED-{tag}")
    return driver


# Runs in the page before any script, on every new document. Wraps fetch
# (the island's only network API on this path) and mirrors the two
# session-critical outcomes into flat globals the gate can poll.
FETCH_RECORDER_JS = (
    "(() => {"
    " const W = window;"
    " W.__wpNet = [];"
    " W.__wpSessionCreated = null;"
    " W.__wpCsrfAdopted = null;"
    " const orig = W.fetch.bind(W);"
    " W.fetch = function (input, init) {"
    "  const url = typeof input === 'string' ? input : (input && input.url) || '';"
    "  const method = String((init && init.method) || (input && input.method) || 'GET').toUpperCase();"
    "  return orig.apply(this, arguments).then((res) => {"
    "   try {"
    "    const path = url.startsWith('http') ? new URL(url).pathname : url;"
    "    if (W.__wpNet.length < 200) W.__wpNet.push(method + ' ' + path + ' -> ' + res.status);"
    "    if (path === '/api/session' && method === 'POST') W.__wpSessionCreated = res.status;"
    "    if (path === '/api/csrf') W.__wpCsrfAdopted = res.status;"
    "   } catch (e) {}"
    "   return res;"
    "  });"
    " };"
    "})();"
)


def wait_session_gate(driver, tag):
    """Demand server-side proof of login: POST /api/session must answer
    201 and the island must re-adopt the rotated CSRF token (GET
    /api/csrf 200). Registration success alone proves nothing here —
    a misconfigured csrf fronting shape 403s the session silently."""
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        session_status, csrf_status = driver.execute_script(
            "return [window.__wpSessionCreated, window.__wpCsrfAdopted]"
        )
        if session_status == 201 and csrf_status == 200:
            say(f"{tag}-SESSION-CREATED")
            say(f"{tag}-CSRF-ADOPTED")
            return
        time.sleep(1)
    net = driver.execute_script("return JSON.stringify(window.__wpNet || [])")
    say(f"{tag}-SESSION-GATE-FAILED: session={session_status} csrf={csrf_status}")
    raise AssertionError(
        f"{tag}: server session not created (POST /api/session -> {session_status}, "
        f"GET /api/csrf -> {csrf_status}); recorded fetches: {net}"
    )


def wait_text(driver, selector, substring, timeout=180):
    # Case-insensitive: the status pill's CSS uppercases its rendered text
    # (Selenium .text returns RENDERED text), so "registered" never
    # matches "REGISTERED" with a plain `in`.
    WebDriverWait(driver, timeout).until(
        lambda d: (
            substring.lower() in d.find_element(By.CSS_SELECTOR, selector).text.lower()
        )
    )


def reg_status(driver):
    try:
        return driver.find_element(By.ID, "reg-status").text
    except WebDriverException:
        return "<no reg-status element>"


def ws_probe(driver, tag):
    # Decisive raw-path experiment: open a plain WebSocket (same origin,
    # same network path as SIP.js) and send a hand-rolled REGISTER.
    # A 401 response proves nginx<->sofia framing works and the problem
    # is SIP.js-specific; silence means the frame path itself is broken.
    probe_js = (
        "const done = arguments[arguments.length - 1];"
        "const events = [];"
        "try {"
        " const ws = new WebSocket('wss://pbx.test/sip', 'sip');"
        " ws.onopen = () => {"
        "  events.push('open');"
        "  ws.send('REGISTER sip:pbx.test SIP/2.0\\r\\n'"
        "    + 'Via: SIP/2.0/WSS pbx.test;branch=z9hG4bKprobe\\r\\n'"
        "    + 'From: <sip:1000@pbx.test>;tag=probe\\r\\n'"
        "    + 'To: <sip:1000@pbx.test>\\r\\n'"
        "    + 'Call-ID: probe-' + Date.now() + '@pbx.test\\r\\n'"
        "    + 'CSeq: 1 REGISTER\\r\\n'"
        "    + 'Max-Forwards: 70\\r\\n'"
        "    + 'Contact: <sip:1000@pbx.test;transport=ws>\\r\\n'"
        "    + 'Content-Length: 0\\r\\n\\r\\n');"
        " };"
        " ws.onmessage = (m) => { events.push('msg:' + String(m.data).slice(0, 200)); done(events); };"
        " ws.onclose = (e) => { events.push('close:' + e.code); done(events); };"
        " ws.onerror = () => events.push('error');"
        " setTimeout(() => done(events.concat('probe-timeout')), 5000);"
        "} catch (e) { events.push('throw:' + e); done(events); }"
    )
    try:
        driver.set_script_timeout(15)
        say(f"{tag}-WS-PROBE: {driver.execute_async_script(probe_js)}")
    except WebDriverException as exc:
        say(f"{tag}-WS-PROBE failed: {exc}")


def dump_driver_state(driver, tag):
    # On-screen evidence: the webphone keeps a #log list (transport and
    # registration events) and the reg-status pill; plus the browser
    # console where WebSocket/CSP errors surface. NOTE: #log sits inside
    # the phone view, which stays hidden while login fails — Selenium's
    # .text returns "" for hidden subtrees, so read textContent instead.
    say(f"{tag}-REG-FAILED-STATUS: {reg_status(driver)}")

    def js(script):
        try:
            return driver.execute_script(script)
        except WebDriverException as exc:
            return f"<js failed: {exc}>"

    log_js = 'return document.getElementById("log").textContent'
    err_js = 'return document.getElementById("login-error").textContent'
    views_js = (
        "return JSON.stringify({"
        '"loginHidden": document.getElementById("login-view").hidden,'
        '"phoneHidden": document.getElementById("phone-view").hidden,'
        '"sip": typeof SIP})'
    )
    ws_js = (
        'return JSON.stringify(performance.getEntriesByType("resource")'
        ".map(r => r.name).filter(n => n.includes('/sip')))"
    )
    say(f"{tag}-LOG:\n{js(log_js)}")
    say(f"{tag}-LOGIN-ERROR: {js(err_js)}")
    ws_probe(driver, tag)
    say(f"{tag}-VIEWS: {js(views_js)}")
    # Did the browser even open the WebSocket to /sip? (Resource timing
    # records wss:// attempts even when the handshake hangs.)
    say(f"{tag}-WS-RESOURCES: {js(ws_js)}")
    try:
        entries = driver.get_log("browser")
        for entry in entries[-40:]:
            say(f"{tag}-CONSOLE {entry['level']}: {entry['message']}")
    except WebDriverException as exc:
        say(f"{tag}-CONSOLE unavailable: {exc}")


def media_bytes(driver, timeout=30):
    """Total inbound RTP bytes across all live peer connections, from the
    browser's own getStats() — proof that real media flows, not just that
    channels exist server-side."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            total = driver.execute_script(
                "const pcs = window.__pcs ? Array.from(window.__pcs.values()) : [];"
                "return Promise.all(pcs.map(pc => pc.getStats())).then(reports => {"
                " let sum = 0;"
                " for (const report of reports)"
                "  for (const stat of report.values())"
                "   if (stat.type === 'inbound-rtp' && stat.kind === 'audio')"
                "    sum += stat.bytesReceived || 0;"
                " return sum;})"
            )
            if total and total > 0:
                return total
        except WebDriverException:
            continue
        time.sleep(1)
    return 0


def login_wrong_password(driver):
    """M11: a wrong password must surface visibly. SIP.js resolves
    register() even on a 403 (it fires Unregistered instead), so the
    webphone lands in the phone view with the rejection pill — accept
    EITHER the #login-error text or the pill's "registration rejected"
    state as proof."""
    say("WRONGPASS-LOGIN-SUBMITTED")
    deadline = time.monotonic() + 150
    while time.monotonic() < deadline:
        err = pill = ""
        try:
            err = driver.execute_script(
                'return document.getElementById("login-error").textContent'
            )
            pill = reg_status(driver)
        except WebDriverException:
            continue
        if err.strip():
            say(f"WRONGPASS-ERROR-SHOWN: {err.strip()[:200]}")
            assert "connect" in err.lower() or "verbind" in err.lower(), err  # nosec B101
            return
        if "rejected" in pill.lower():
            say(f"WRONGPASS-PILL-REJECTED: {pill}")
            return
        time.sleep(2)
    raise AssertionError(
        "wrong-password leg showed neither #login-error nor the rejected pill"
    )


def theme_fouc_check():
    """webphone theme preload (2026-09-23): a forced dark choice must be
    on <html> BEFORE first paint, or a light-OS user flashes the wrong
    theme every load. Evidence pair under a throttled network (400ms
    latency, 50 KB/s — on localhost the flash window is unmeasurably
    narrow) with prefers-color-scheme emulated LIGHT and wp-theme=dark
    seeded:

      preload BLOCKED  -> body ticks without data-theme must be
                          observable in-page (the flash the preload
                          kills), and the page must still settle dark
                          (shell.js re-applies; a missing preload must
                          not strand the user in the OS theme).
      preload ALLOWED  -> every body tick already reads dark; a body
                          tick without the attribute is a FOUC
                          regression.

    Ticks are BODY-GATED and counted IN-PAGE (rAF + interval recorder
    via Page.addScriptToEvaluateOnNewDocument): chromedriver will not
    run scripts against a document mid-navigation, so a driver-side
    poll can only ever see the settled document — the unthemed window
    inside a reload is invisible to it (live evidence 2026-09-23:
    three runs sampled unbroken "dark" while nginx proved the blocked
    reload had really happened)."""
    say("THEME-CHECK-START")
    driver = make_driver("theme")
    try:
        driver.get("https://pbx.test/")
        WebDriverWait(driver, 180).until(
            EC.presence_of_element_located((By.ID, "login-form"))
        )
        driver.execute_cdp_cmd(
            "Emulation.setEmulatedMedia",
            {"features": [{"name": "prefers-color-scheme", "value": "light"}]},
        )
        driver.execute_script("localStorage.setItem('wp-theme', 'dark');")
        driver.execute_cdp_cmd("Network.enable", {})
        # The wrongpass load warmed the HTTP cache, and a plain
        # location.reload() serves heuristically-fresh subresources
        # FROM CACHE — where blocked URLs cannot intercept them (live
        # evidence 2026-09-23: the reload's resource timing showed
        # theme-preload.js "done" while nginx never saw a request for
        # it, so the preload executed anyway and no flash was
        # possible). Network.setCacheDisabled did NOT change this
        # through chromedriver; the reloads below therefore use
        # Page.reload with ignoreCache, which re-fetches every
        # subresource over the throttled network where the URL block
        # can bite.
        driver.execute_cdp_cmd(
            "Network.setCacheDisabled", {"cacheDisabled": True}
        )
        driver.execute_cdp_cmd(
            "Network.emulateNetworkConditions",
            {
                "offline": False,
                "latency": 400,
                # 200 KB/s keeps each throttled reload under ~10s (the
                # E2E wall-time budget is 445s) while leaving a window of
                # seconds between first paint and shell.js — 50ms sampling
                # cannot miss it.
                "downloadThroughput": 200 * 1024,
                "uploadThroughput": 200 * 1024,
            },
        )

        # In-page recorder: counts body-present ticks by theme state
        # from document-start of every navigation — a paint-approximate
        # rAF ticker plus a time-based interval backstop in case the
        # headless compositor throttles rAF. A driver-side poll cannot
        # see mid-navigation states; see the docstring.
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "window.__wpTheme = {rafUnthemed: 0, rafThemed: 0,"
                    " ivlUnthemed: 0, ivlThemed: 0};"
                    "(function rafTick() {"
                    "  try { if (document.body) {"
                    "    if (document.documentElement.getAttribute('data-theme'))"
                    "      window.__wpTheme.rafThemed++;"
                    "    else window.__wpTheme.rafUnthemed++;"
                    "  } } catch (e) {}"
                    "  requestAnimationFrame(rafTick);"
                    "})();"
                    "setInterval(function () {"
                    "  try { if (document.body) {"
                    "    if (document.documentElement.getAttribute('data-theme'))"
                    "      window.__wpTheme.ivlThemed++;"
                    "    else window.__wpTheme.ivlUnthemed++;"
                    "  } } catch (e) {}"
                    "}, 16);"
                )
            },
        )

        def kick_reload():
            # ignoreCache (hard reload): a soft reload serves cached
            # subresources that Network.setBlockedURLs cannot touch —
            # see the comment above the cache-disable call.
            driver.execute_cdp_cmd("Page.reload", {"ignoreCache": True})

        def settle_after_reload():
            # Deferred scripts run before DOMContentLoaded, so once the
            # login form is back the theme has settled; half a second
            # more lets late rAF ticks land before reading counters.
            WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.ID, "login-form"))
            )
            time.sleep(0.5)
            return driver.execute_script(
                "var t = window.__wpTheme || {};"
                "return [t.rafUnthemed || 0, t.rafThemed || 0,"
                " t.ivlUnthemed || 0, t.ivlThemed || 0,"
                " document.documentElement.getAttribute('data-theme') || '']"
            )

        # Pair 1 — preload BLOCKED: unthemed body ticks must exist (the
        # flash the preload kills), then shell.js must still settle dark.
        driver.execute_cdp_cmd(
            "Network.setBlockedURLs", {"urls": ["*theme-preload.js"]}
        )
        kick_reload()
        raf_u, raf_t, ivl_u, ivl_t, final_theme = settle_after_reload()
        say(
            f"THEME-PAIR1-TICKS rafUnthemed={raf_u} rafThemed={raf_t}"
            f" ivlUnthemed={ivl_u} ivlThemed={ivl_t} final={final_theme}"
        )
        if raf_u <= 0 and ivl_u <= 0:
            raise AssertionError(
                "blocked preload never left the body unthemed — the "
                "preload is not observable as load-bearing"
            )
        if final_theme != "dark":
            raise AssertionError(
                "blocked preload stranded the page off-theme; shell.js "
                "must re-apply dark after load"
            )
        say("THEME-BLOCKED-FLASH-THEN-DARK")

        # Pair 2 — preload ALLOWED: no body tick may ever lack the theme.
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": []})
        kick_reload()
        raf_u, raf_t, ivl_u, ivl_t, final_theme = settle_after_reload()
        say(
            f"THEME-PAIR2-TICKS rafUnthemed={raf_u} rafThemed={raf_t}"
            f" ivlUnthemed={ivl_u} ivlThemed={ivl_t} final={final_theme}"
        )
        if raf_u > 0 or ivl_u > 0:
            raise AssertionError(
                "FOUC regression: body ticks without data-theme while "
                "the preload was enabled"
            )
        if final_theme != "dark":
            raise AssertionError("themed settle never happened under throttle")
        say("THEME-PRELOAD-NO-FLASH")
        say("THEME-CHECK-DONE")
    finally:
        try:
            driver.quit()
        except Exception as exc:  # noqa: BLE001
            print(f"quit failed: {exc}", file=sys.stderr, flush=True)


def reconnect_drill(driver):
    """M11: kill the transport mid-session (the testScript stops nginx on
    the RECONNECT-READY marker), watch the pill show the reconnect
    backoff, then recover to registered."""
    say("RECONNECT-READY")
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        status = reg_status(driver).lower()
        if "reconnect" in status:
            say(f"RECONNECT-DETECTED: {status}")
            break
        time.sleep(2)
    else:
        raise AssertionError(f"pill never showed reconnecting: {reg_status(driver)}")
    # sip.js 0.21's userAgent.reconnect() can hang forever after a
    # transport loss; the app bounds every attempt with a watchdog and
    # rebuilds the connection when one hangs — give the automatic
    # recovery (attempt + rebuild, worst case) room to prove itself.
    # The testScript restarts nginx once RECONNECT-DETECTED is logged.
    time.sleep(25)
    if "registered" in reg_status(driver).lower():
        say("RECONNECTED-AUTO")
        return
    # Belt and braces: if auto-recovery still fails, the path users
    # actually have — reload the page — must work.
    say(f"RECONNECT-AUTO-STUCK: {reg_status(driver)} — recovering via reload")
    recover_via_reload(driver, "1000")
    say("RECONNECTED")


def recover_via_reload(driver, extension):
    """The recovery path every user has: reload the page, log in again.
    Also used outside the drill for a callee whose own auto-reconnect
    hung (the known SIP.js 0.21 reconnect() bug can wedge either page).
    A live cookie session RESUMES without the login form (the SQLite
    store survives service restarts), so the form is only filled when
    it is actually shown — filling it blindly crashed the 2026-09-22
    run on the hidden #ext (ElementNotInteractable).
    """
    driver.get("https://pbx.test/")
    WebDriverWait(driver, 180).until(
        EC.presence_of_element_located((By.ID, "login-form"))
    )
    ext = driver.find_element(By.ID, "ext")
    if ext.is_displayed():
        driver.find_element(By.ID, "pass").send_keys(PASSWORDS[extension])
        ext.send_keys(extension)
        driver.find_element(By.ID, "login-form").submit()
    wait_text(driver, "#reg-status", "registered", timeout=120)


def wait_file(path, timeout=180):
    """Block until the testScript touches `path` (its side of a phase)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.exists(path):
            return
        time.sleep(1)
    raise AssertionError(f"testScript never created {path}")


def click_tab(driver, tab):
    """Click a nav tab and wait for the partial to swap in.

    Transient toasts (transfer verdicts, call-ended notices) overlay
    the nav bar for a few seconds and can intercept the click (run 5
    died exactly there). Retry until the click lands; the retry only
    re-runs while the click itself throws, so a landed click is never
    doubled."""

    def click_lands(d):
        try:
            d.find_element(By.CSS_SELECTOR, f"[data-tab='{tab}']").click()
            return True
        except ElementClickInterceptedException:
            return False

    WebDriverWait(driver, 60).until(click_lands)
    WebDriverWait(driver, 60).until(
        lambda d: d.find_element(By.ID, "tab-content").find_elements(
            By.CSS_SELECTOR, ".wp-panel"
        )
    )


def no_dead_session_toast(driver):
    """The session-persistence contract (webphone T12): after a webphone
    RESTART the tab session must still be live — the throttled
    dead-session toast must NOT appear."""
    toasts_text = driver.find_element(By.ID, "toasts").text.lower()
    assert "session ended" not in toasts_text, (
        f"dead-session toast fired: {toasts_text}"
    )


def contacts_roundtrip(driver):
    """webphone T20g: personal-contact create -> row -> delete -> gone,
    through the real UI (form post + panel swap). The number is chosen
    so no shared-directory entry or test call produces a lookalike row."""
    click_tab(driver, "contacts")
    name = "E2E Probe"
    number = "+498990001234"
    form = driver.find_element(By.CSS_SELECTOR, "form.wp-compose-new")
    form.find_element(By.CSS_SELECTOR, "input[name='name']").send_keys(name)
    form.find_element(By.CSS_SELECTOR, "input[name='number']").send_keys(number)
    form.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    WebDriverWait(driver, 60).until(
        lambda d: next(
            (
                r
                for r in d.find_elements(By.CSS_SELECTOR, "article.wp-row")
                if name in r.text and number in r.text
            ),
            None,
        )
    )
    # Delete needs the hx-confirm dialog answered before htmx posts.
    row = next(
        r
        for r in driver.find_elements(By.CSS_SELECTOR, "article.wp-row")
        if name in r.text and number in r.text
    )
    row.find_element(By.CSS_SELECTOR, ".wp-danger").click()
    WebDriverWait(driver, 10).until(EC.alert_is_present())
    driver.switch_to.alert.accept()
    WebDriverWait(driver, 60).until(
        lambda d: not any(
            number in r.text
            for r in d.find_elements(By.CSS_SELECTOR, "article.wp-row")
        )
    )


def webphone_restart_drill(driver):
    """webphone T07: the service restarts mid-session (testScript does the
    systemctl restart on the RESTART-READY marker); the open tab must
    keep working WITHOUT re-login and WITHOUT the dead-session toast —
    the session store is SQLite-backed now."""
    say("RESTART-READY")
    wait_file("/tmp/webphone-restarted")
    click_tab(driver, "messages")
    no_dead_session_toast(driver)
    say("RESTART-SESSION-KEPT")


def dial_into_call(caller, callee, tag, attempts=2):
    """Dial 1001 from 1000 with a reload-retry: a fresh dial after a
    teardown is exactly the wedged-transport class this suite keeps
    hitting (the callee's WS can be half-dead while sofia still lists
    the registration)."""
    for attempt in range(attempts):
        # Clear first: the island does not always empty #dest after a
        # dial, and send_keys APPENDS — the unallocated-transfer drill
        # used to leave "1001" behind so this dialed "10011001" and
        # silently burned the retry (found 2026-09-22, runs 1+2).
        dest = caller.find_element(By.ID, "dest")
        dest.clear()
        dest.send_keys("1001")
        caller.find_element(By.ID, "dial-form").submit()
        say(f"DIAL-{tag}-{attempt}-SUBMITTED")
        try:
            wait_text(callee, "#incoming-from", "1000", timeout=60)
            break
        except Exception:
            if attempt == attempts - 1:
                raise
            dump_driver_state(caller, f"1000-redial-{tag}")
            dump_driver_state(callee, f"1001-redial-{tag}")
            recover_via_reload(caller, "1000")
            recover_via_reload(callee, "1001")
    callee.find_element(By.ID, "accept-btn").click()
    wait_text(caller, ".call-state-text", "in call", timeout=60)
    say(f"CALL-{tag}-ESTABLISHED")


def unallocated_transfer_drill(caller, callee):
    """webphone T10 (converted, run-3 evidence): the stack dialplan has a
    catch_all that hangs unallocated numbers up, so a REFER to an
    unknown destination COMPLETES as a transfer and the transferred leg
    dies at `unallocated_number` — no failure sipfrag is reachable by
    destination choice. What this scenario pins is the verdict path
    itself: the island must surface the network's NOTIFY sipfrag verdict
    in #log and BOTH legs must end up clearly terminated (transferer
    released; transferred leg hung up by the dialplan)."""
    caller.find_element(By.CSS_SELECTOR, ".transfer-btn").click()
    caller.find_element(By.CSS_SELECTOR, ".transfer-dest").send_keys("9999")
    # renderCalls can rebuild the card between reveal and confirm; retry
    # the confirm click, re-opening the row if a re-render hid it.
    for attempt in range(6):
        row = caller.find_elements(By.CSS_SELECTOR, ".transfer-row button")
        if row:
            row[0].click()
            break
        caller.find_element(By.CSS_SELECTOR, ".transfer-btn").click()
        caller.find_element(By.CSS_SELECTOR, ".transfer-dest").send_keys("9999")
        time.sleep(0.5)
    say("TRANSFER-UNALLOCATED-INITIATED")

    def verdict_logged(d):
        # textContent, not .text: the log lives in a closed <details>, so
        # Selenium's rendered-text is empty no matter what was logged.
        text = d.execute_script(
            "var el = document.getElementById('log');"
            "return el ? el.textContent.toLowerCase() : '';"
        )
        return "transfer completed" in text or "transfer failed" in text

    # 300s: the final NOTIFY tracks the transferred leg's dialplan
    # outcome, which can lag minutes under VM load (runs 9-10 evidence).
    WebDriverWait(caller, 300).until(verdict_logged)

    def caller_cards_gone(d):
        cards = d.find_elements(By.CSS_SELECTOR, ".call-card")
        if not cards:
            return True
        if not hasattr(caller, "_zombie_logged"):
            caller._zombie_logged = True
            print(
                "ZOMBIE-CARD-DIAG: "
                + d.execute_script("return document.getElementById('calls').outerHTML"),
                flush=True,
            )
        return False

    WebDriverWait(caller, 120).until(caller_cards_gone)

    # The transferee's dialog persists (FS re-INVITEd it toward 9999 and
    # its hangup can lag minutes), so the callee actively hangs the stale
    # call up — otherwise the next dial would be rejected as a second
    # incoming call.
    hangup = callee.find_elements(By.CSS_SELECTOR, ".hangup-btn")
    if hangup:
        hangup[0].click()
        WebDriverWait(callee, 60).until(
            lambda d: not d.find_elements(By.CSS_SELECTOR, ".call-card")
        )
    say("TRANSFER-VERDICT-SURFACED")


def fs_outage_drill(caller, callee):
    """webphone T09: FreeSWITCH stops mid-call (testScript side), the
    island must SAY something (reconnecting/offline pill, failure in
    #log) instead of silently showing a zombie call, and it must recover
    to registered once FreeSWITCH returns. Rides the live call that
    dial_into_call just established."""
    say("FS-OUTAGE-READY")
    wait_file("/tmp/fs-outage-on")

    def outage_visible(d):
        status = reg_status(d).lower()
        if any(w in status for w in ("reconnect", "offline", "disconnected")):
            return True
        return "failed" in d.find_element(By.ID, "log").text.lower() or (
            not d.find_elements(By.CSS_SELECTOR, ".call-card")
        )

    WebDriverWait(caller, 120).until(outage_visible)
    say("FS-OUTAGE-DETECTED")
    wait_file("/tmp/fs-recovered", timeout=600)
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        if "registered" in reg_status(caller).lower():
            break
        time.sleep(3)
    else:
        recover_via_reload(caller, "1000")
    say("FS-RECOVERED")
    # Any surviving call card on either side must go before E2E-OK.
    for d in (caller, callee):
        hangup = d.find_elements(By.CSS_SELECTOR, ".hangup-btn")
        if hangup:
            hangup[0].click()
    time.sleep(5)


def login(driver, extension):
    say(f"{extension}-DRIVER-GET")
    driver.get("https://pbx.test/")
    WebDriverWait(driver, 180).until(
        EC.presence_of_element_located((By.ID, "login-form"))
    )
    say(f"{extension}-PAGE-LOADED")
    driver.find_element(By.ID, "ext").send_keys(extension)
    driver.find_element(By.ID, "pass").send_keys(PASSWORDS[extension])
    driver.find_element(By.ID, "login-form").submit()
    say(f"{extension}-LOGIN-SUBMITTED")
    try:
        wait_text(driver, "#reg-status", "registered")
    except Exception:
        # Registration state, the webphone's own log list and the browser
        # console localise the failing half (page/transport/auth) before
        # re-raising.
        dump_driver_state(driver, extension)
        raise
    say(f"{extension}-REGISTERED")


def main():
    # --- M11: wrong password surfaces an on-screen error ---
    wrong = make_driver("wrongpass")
    try:
        wrong.get("https://pbx.test/")
        WebDriverWait(wrong, 180).until(
            EC.presence_of_element_located((By.ID, "login-form"))
        )
        wrong.find_element(By.ID, "ext").send_keys("1000")
        wrong.find_element(By.ID, "pass").send_keys("definitely-wrong")
        wrong.find_element(By.ID, "login-form").submit()
        login_wrong_password(wrong)
        say("WRONGPASS-DONE")
    finally:
        try:
            wrong.quit()
        except Exception as exc:  # noqa: BLE001
            print(f"quit failed: {exc}", file=sys.stderr, flush=True)

    # --- webphone theme preload: FOUC evidence pair (throttled) ---
    theme_fouc_check()

    caller = make_driver("1000")
    callee = make_driver("1001")
    try:
        login(caller, "1000")
        wait_session_gate(caller, "1000")
        login(callee, "1001")
        wait_session_gate(callee, "1001")

        # --- webphone T07: the service restarts mid-session; the tab
        # session (SQLite store) must survive it without a re-login or
        # the dead-session toast ---
        webphone_restart_drill(caller)

        # --- M11: reconnect drill (nginx is stopped/started by the
        # testScript between the markers) ---
        reconnect_drill(caller)

        # Post-recovery settle: a dial racing the callee's re-REGISTER
        # can hit its stale pre-loss contact and die at ring timeout,
        # and the callee's own auto-reconnect may be the wedged one
        # (known SIP.js bug) — give each page a short window to settle,
        # then fall back to the reload recovery.
        for d, ext in ((caller, "1000"), (callee, "1001")):
            deadline = time.monotonic() + 10
            while (
                time.monotonic() < deadline
                and "registered" not in reg_status(d).lower()
            ):
                time.sleep(1)
            if "registered" not in reg_status(d).lower():
                recover_via_reload(d, ext)

        # Dial 1001 from 1000; the callee banner must name the caller.
        try:
            dest = caller.find_element(By.ID, "dest")
            dest.clear()
            dest.send_keys("1001")
            caller.find_element(By.ID, "dial-form").submit()
            say("DIAL-SUBMITTED")
            wait_text(callee, "#incoming-from", "1000", timeout=60)
            say("INCOMING-SHOWN")

            # --- Incoming-call UX: the tab title flashes while ringing ---
            def title_flashing(d):
                return d.execute_script("return document.title") != "PBX WebPhone"

            WebDriverWait(callee, 20).until(title_flashing)
            say("TITLE-FLASHING")

            # Notification permission was requested at login (headless
            # chromium may grant or deny; either state is logged).
            def notif_logged(d):
                return "notifications" in d.execute_script(
                    'return document.getElementById("log").textContent'
                )

            # Notification permission is requested from the LOGIN click
            # (a user gesture); a page that RESUMED a live session this
            # boot never logs in, so the permission log line cannot
            # exist there — the marker is conditional on the boot mode.
            if callee.find_element(By.ID, "login-form").is_displayed():
                WebDriverWait(callee, 30).until(notif_logged)
                say("NOTIF-PERMISSION-LOGGED")
            else:
                say("NOTIF-SKIPPED-RESUMED-BOOT")

            callee.find_element(By.ID, "accept-btn").click()

            # TEMP-DIAG (webphone answer-stall hunt 2026-09-18): on any
            # failure in the answer phase, dump both browsers' island #log
            # and call-card states before dying, then re-raise.
            def dump_answer_phase(step):
                for name, drv in (("1000", caller), ("1001", callee)):
                    try:
                        info = drv.execute_script(
                            "return JSON.stringify({log: document.getElementById('log').textContent,"
                            " states: [...document.querySelectorAll('.call-state-text')].map(e => e.textContent),"
                            " incomingHidden: document.getElementById('incoming-call')?.hidden,"
                            " diag: window.__wpDiag})"
                        )
                        say(f"DIAG-ANSWER-{name}-{step}: {info}")
                    except Exception as inner:
                        say(f"DIAG-ANSWER-{name}-{step}-FAILED: {inner}")

            try:
                wait_text(caller, ".call-state-text", "in call", timeout=60)
                wait_text(callee, ".call-state-text", "in call", timeout=60)
            except Exception:
                dump_answer_phase("stalled")
                raise
            say("CALL-ESTABLISHED")

            # --- M9: real media proof via getStats on both browsers ---
            # media_bytes returns on the FIRST nonzero sample, and the two
            # directions ramp at different times right after "in call";
            # a one-shot pair of asserts fails the slower side mid-ramp.
            # Poll until BOTH sides provably stream (or the window closes).
            media_deadline = time.monotonic() + 45
            caller_bytes = callee_bytes = 0
            while time.monotonic() < media_deadline:
                caller_bytes, callee_bytes = media_bytes(caller), media_bytes(callee)
                if caller_bytes > 1000 and callee_bytes > 1000:
                    break
                time.sleep(3)
            say(f"MEDIA-BYTES caller={caller_bytes} callee={callee_bytes}")
            assert caller_bytes > 1000, f"caller received no RTP: {caller_bytes}"  # nosec B101
            assert callee_bytes > 1000, f"callee received no RTP: {callee_bytes}"  # nosec B101

            # --- M11: DTMF keypad sends a tone on the live call ---
            caller.find_element(
                By.CSS_SELECTOR, '#keypad button[data-tone="5"]'
            ).click()

            def dtmf_logged(d):
                log_text = d.execute_script(
                    'return document.getElementById("log").textContent'
                )
                return "dtmf 5" in log_text

            WebDriverWait(caller, 30).until(dtmf_logged)
            say("DTMF-SENT")

            # Keep the call up while the testScript asserts the bridge and
            # media server-side (fs_cli show channels / detailed_calls).
            time.sleep(10)

            # --- ICE/media diagnostics panel: live stats for the focus call ---
            caller.find_element(By.CSS_SELECTOR, "#ice-wrap summary").click()

            def ice_stats_present(d):
                return "ice:" in d.find_element(By.ID, "ice-panel").text

            WebDriverWait(caller, 45).until(ice_stats_present)
            say("ICE-PANEL-SHOWN")

            # --- webphone T20h: the header call badge mirrors the live
            # call on every tab (presence without reading the panel) ---
            WebDriverWait(caller, 30).until(
                lambda d: "on call" in d.find_element(By.ID, "call-badge").text
            )
            say("BADGE-LIVE")

            # --- webphone T10: transfer to an unallocated number — the
            # NOTIFY sipfrag verdict must surface in #log, and both legs
            # must end clearly ---
            unallocated_transfer_drill(caller, callee)

            # --- webphone T09: FreeSWITCH outage mid-call, then recovery
            # (testScript stops/starts the unit on the file markers) ---
            dial_into_call(caller, callee, "OUTAGE")
            fs_outage_drill(caller, callee)

            # --- P8: blind transfer moves the callee leg to the echo test ---
            # The caller REFERs its call to 9196; FreeSWITCH re-routes the
            # PARTNER leg (1001) into the echo application and releases the
            # transferer — desk-phone semantics, executed server-side.
            dial_into_call(caller, callee, "BLIND")

            def transfer_dbg(what):
                row = caller.execute_script(
                    "var r=document.querySelector('.transfer-row');"
                    "return r?r.outerHTML:'MISSING';"
                )
                print(
                    f"TRANSFER-DBG {time.strftime('%H:%M:%S')} {what}: {row}",
                    flush=True,
                )

            caller.find_element(By.CSS_SELECTOR, ".transfer-btn").click()
            transfer_dbg("after transfer-btn click")
            caller.find_element(By.CSS_SELECTOR, ".transfer-dest").send_keys("9196")
            transfer_dbg("after send_keys")
            caller.find_element(By.CSS_SELECTOR, ".transfer-row button").click()
            say("TRANSFER-BLIND-INITIATED")
            WebDriverWait(caller, 60).until(
                lambda d: not d.find_elements(By.CSS_SELECTOR, ".call-card")
            )
            say("TRANSFER-CALLER-RELEASED")
            # The callee stays established (now echo-bound) and keeps
            # receiving media (its own noise streamed back).
            wait_text(callee, ".call-state-text", "in call", timeout=60)
            callee_media = 0
            callee_deadline = time.monotonic() + 30
            while time.monotonic() < callee_deadline:
                callee_media = media_bytes(callee)
                if callee_media > 1000:
                    break
                time.sleep(2)
            say(f"TRANSFER-CALLEE-MEDIA bytes={callee_media}")
            assert callee_media > 1000, f"callee echo stream lost: {callee_media}"  # nosec B101

            callee.find_element(By.CSS_SELECTOR, ".hangup-btn").click()
            WebDriverWait(callee, 60).until(
                lambda d: not d.find_elements(By.CSS_SELECTOR, ".call-card")
            )

            # --- webphone T20g/T20f tail: the contacts round-trip on the
            # caller, then the logged-out data-dial guard on a fresh
            # short-lived session. The guard registers LATE (the sofia
            # binding-count asserts already ran) and quits before
            # E2E-OK, so it cannot disturb the call flow above. ---
            contacts_roundtrip(caller)
            say("CONTACTS-ROUNDTRIP-OK")
            guard = make_driver("dialguard")
            try:
                login(guard, "1000")
                wait_session_gate(guard, "dialguard")
                click_tab(guard, "contacts")
                # Seed one contact: the roundtrip above deletes its
                # probe row, and a fresh profile starts with an empty
                # personal list — the guarded click needs a real
                # data-dial button in the DOM.
                form = guard.find_element(
                    By.CSS_SELECTOR, "form.wp-compose-new"
                )
                form.find_element(
                    By.CSS_SELECTOR, "input[name='name']"
                ).send_keys("Guard Probe")
                form.find_element(
                    By.CSS_SELECTOR, "input[name='number']"
                ).send_keys("+498990005555")
                form.find_element(
                    By.CSS_SELECTOR, "button[type='submit']"
                ).click()
                WebDriverWait(guard, 60).until(
                    lambda d: d.find_elements(By.CSS_SELECTOR, "[data-dial]")
                )
                # A real sign-out RELOADS to the login-card shell
                # (session.js), so no data-dial surface can survive
                # it. The guard exists for the in-place signed-out
                # island (session expiry mid-tab): #phone-view hidden
                # while the tab partial is still on screen. Reproduce
                # that exact DOM state and prove the delegated
                # handler degrades to a toast + login-field focus,
                # never a dead submit.
                guard.execute_script(
                    "document.getElementById('phone-view').hidden = true;"
                    "document.getElementById('login-view').hidden = false"
                )
                guard.find_element(By.CSS_SELECTOR, "[data-dial]").click()
                WebDriverWait(guard, 30).until(
                    lambda d: "signed out"
                    in d.find_element(By.ID, "toasts").text.lower()
                )
                focused = guard.execute_script(
                    "return document.activeElement && document.activeElement.id"
                )
                assert focused == "ext", (  # nosec B101
                    f"#ext not focused after guarded dial: {focused!r}"
                )
                # And the real logout leaves no dead-submit surface
                # behind: the reload lands on the login-card shell
                # with zero data-dial buttons in the DOM.
                guard.execute_script(
                    "document.getElementById('phone-view').hidden = false;"
                    "document.getElementById('login-view').hidden = true"
                )
                guard.find_element(By.ID, "logout").click()
                WebDriverWait(guard, 60).until(
                    EC.visibility_of_element_located((By.ID, "login-view"))
                )
                leftovers = guard.find_elements(
                    By.CSS_SELECTOR, "[data-dial]"
                )
                assert not leftovers, (  # nosec B101
                    f"data-dial buttons survived logout: {len(leftovers)}"
                )
                say("LOGGED-OUT-DIAL-GUARDED")
            finally:
                try:
                    guard.quit()
                except Exception as exc:  # noqa: BLE001
                    print(f"quit failed: {exc}", file=sys.stderr, flush=True)

            say("E2E-OK")
        except Exception:
            # Call-phase evidence: both webphone log lists (outgoing/incoming
            # legs, ICE/transport errors) and consoles, before re-raising.
            dump_driver_state(caller, "1000-call")
            dump_driver_state(callee, "1001-call")
            raise
    except Exception:
        # Pre-call-phase evidence (restart/reconnect drills): both
        # pages' island #log and reg-status pills. The 2026-09-22 run-1
        # failure lost ALL browser state because only the call phase
        # dumped.
        for name, drv in (("1000", caller), ("1001", callee)):
            try:
                dump_driver_state(drv, f"{name}-precall")
            except Exception as exc:  # noqa: BLE001 - best-effort evidence
                print(
                    f"precall dump failed for {name}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
        raise
    finally:
        for driver in (caller, callee):
            try:
                driver.quit()
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup
                print(f"quit failed: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        # The traceback is the primary evidence for a stalled marker; make
        # sure it reaches /tmp/e2e.log before the non-zero exit.
        traceback.print_exc()
        sys.stdout.flush()
        raise
