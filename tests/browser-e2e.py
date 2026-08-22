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
import sys
import time
import traceback

from selenium import webdriver
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
        log_output=f"/tmp/chromedriver-{tag}.log",
    )
    driver = webdriver.Chrome(service=service, options=options)
    say(f"DRIVER-STARTED-{tag}")
    return driver


def wait_text(driver, selector, substring, timeout=180):
    # Case-insensitive: the status pill's CSS uppercases its rendered text
    # (Selenium .text returns RENDERED text), so "registered" never
    # matches "REGISTERED" with a plain `in`.
    WebDriverWait(driver, timeout).until(
        lambda d: substring.lower()
        in d.find_element(By.CSS_SELECTOR, selector).text.lower()
    )


def reg_status(driver):
    try:
        return driver.find_element(By.ID, "reg-status").text
    except Exception:
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
    except Exception as exc:
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
        except Exception as exc:
            return f"<js failed: {exc}>"

    log_js = 'return document.getElementById("log").textContent'
    err_js = 'return document.getElementById("login-error").textContent'
    views_js = (
        'return JSON.stringify({'
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
    except Exception as exc:
        say(f"{tag}-CONSOLE unavailable: {exc}")


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
    caller = make_driver("1000")
    callee = make_driver("1001")
    try:
        login(caller, "1000")
        login(callee, "1001")

        # Dial 1001 from 1000; the callee banner must name the caller.
        try:
            caller.find_element(By.ID, "dest").send_keys("1001")
            caller.find_element(By.ID, "dial-form").submit()
            say("DIAL-SUBMITTED")
            wait_text(callee, "#incoming-from", "1000", timeout=60)
            say("INCOMING-SHOWN")

            callee.find_element(By.ID, "accept-btn").click()
            wait_text(caller, ".call-state-text", "in call", timeout=60)
            wait_text(callee, ".call-state-text", "in call", timeout=60)
            say("CALL-ESTABLISHED")

            # Keep the call up while the testScript asserts the bridge and
            # media server-side (fs_cli show channels / detailed_calls).
            time.sleep(15)

            caller.find_element(By.CSS_SELECTOR, ".hangup-btn").click()
            WebDriverWait(caller, 60).until(
                lambda d: not d.find_elements(By.CSS_SELECTOR, ".call-card")
            )
            WebDriverWait(callee, 60).until(
                lambda d: not d.find_elements(By.CSS_SELECTOR, ".call-card")
            )
            say("E2E-OK")
        except Exception:
            # Call-phase evidence: both webphone log lists (outgoing/incoming
            # legs, ICE/transport errors) and consoles, before re-raising.
            dump_driver_state(caller, "1000-call")
            dump_driver_state(callee, "1001-call")
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
