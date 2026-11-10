# ruff: noqa: N999 - VM-deployed script, the hyphenated name is a suite contract
"""Browser leg of the passkey ceremony E2E (on-demand lane, telephony-passkey).

Drives the REAL WebAuthn ceremony end to end inside headless chromium:
a CDP virtual authenticator answers the ceremonies, so no human and no
hardware is involved — enroll (one-time token from the CLI) and then
login (the library-owned /login page) through the same surfaces a user
touches. Runs SOLO by the browser-E2E rule (concurrent VM builds
reproduce the load-flake class).

Markers land in this script's log (/tmp/passkey-e2e.log):
  ENROLL-CEREMONY-DONE  the create ceremony finished, passkey registered
  PASSKEY-E2E-DONE      the get ceremony finished, session gate answered 200
"""

import sys
import threading

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CHROMEDRIVER = "@chromedriver@"
CHROMIUM = "@chromium@"
BASE = "https://pbx.test"
EMAIL = "alice@pbx.test"


def say(marker):
    print(marker, flush=True)


def make_driver(tag):
    options = ChromeOptions()
    options.binary_location = CHROMIUM
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    # The PBX vhost serves a runtime self-signed certificate.
    options.add_argument("--ignore-certificate-errors")
    options.set_capability("acceptInsecureCerts", True)
    options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
    options.add_argument("--window-size=1280,900")
    # Session creation can HANG (the 2026-10-25 wedged-negotiation class):
    # bound every attempt with a watchdog thread like browser-e2e.py.
    driver = None
    for attempt in range(1, 4):
        suffix = "" if attempt == 1 else f"-retry{attempt}"
        service = Service(
            executable_path=CHROMEDRIVER,
            service_args=["--verbose"],
            log_output=f"/tmp/chromedriver-passkey-{tag}{suffix}.log",  # nosec B108 - test log
        )
        box = {}

        def _construct(box=box, service=service, options=options):
            try:
                box["driver"] = webdriver.Chrome(service=service, options=options)
            except BaseException as exc:  # noqa: BLE001
                box["error"] = exc

        thread = threading.Thread(target=_construct, daemon=True)
        thread.start()
        thread.join(60)
        if thread.is_alive():
            say(f"DRIVER-START-TIMEOUT-{tag}-{attempt}")
            try:
                service.stop()
            except Exception:  # noqa: BLE001,S110
                pass
            thread.join(10)
            continue
        if "error" in box:
            raise box["error"]
        driver = box["driver"]
        break
    if driver is None:
        raise AssertionError(f"chromedriver session creation stalled 3x for {tag}")
    return driver


def attach_virtual_authenticator(driver):
    """A ctap2/internal authenticator answers every ceremony silently."""
    driver.execute_cdp_cmd("WebAuthn.enable", {})
    driver.execute_cdp_cmd(
        "WebAuthn.addVirtualAuthenticator",
        {
            "options": {
                "protocol": "ctap2",
                "transport": "internal",
                "automaticPresenceSimulation": True,
                "isUserVerified": True,
            }
        },
    )


def main():
    token = sys.argv[1]
    assert token, "usage: passkey-e2e.py <enroll-token>"

    driver = make_driver("main")
    try:
        attach_virtual_authenticator(driver)

        # --- Enroll: the CLI link carries the one-time token; the page
        # prefills it and the create ceremony runs on submit. The virtual
        # authenticator answers the navigator.credentials.create prompt.
        driver.get(f"{BASE}/enroll?token={token}")
        token_input = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "enroll-token"))
        )
        assert token_input.get_attribute("value") == token, (
            f"enroll token not prefilled: {token_input.get_attribute('value')!r}"
        )
        driver.find_element(By.ID, "enroll-credential-name").send_keys(
            "vm-virtual-authenticator"
        )
        driver.find_element(By.ID, "enroll-form").submit()
        WebDriverWait(driver, 60).until(
            lambda d: d.find_element(By.ID, "enroll-status").is_displayed()
        )
        status = driver.find_element(By.ID, "enroll-status")
        error = driver.find_element(By.ID, "enroll-error")
        assert error.get_attribute("hidden"), f"enroll error surfaced: {error.text!r}"
        say(f"ENROLL-CEREMONY-DONE status={status.text!r}")

        # --- Login: the library-owned /login page. Fill the email, click
        # the passkey button; the get ceremony resolves against the
        # credential the enroll ceremony just created, then the page
        # redirects to the shell.
        driver.get(BASE)
        WebDriverWait(driver, 60).until(
            EC.element_to_be_clickable((By.ID, "passkey-login"))
        ).click()
        email_input = WebDriverWait(driver, 60).until(
            EC.presence_of_element_located((By.ID, "lp-email"))
        )
        email_input.send_keys(EMAIL)
        WebDriverWait(driver, 60).until(
            EC.element_to_be_clickable((By.ID, "lp-login-btn"))
        ).click()
        # Success = redirect to the shell (config.redirect = "/"). Any
        # ceremony rejection lands in #lp-error instead — assert its
        # absence AFTER the redirect (the element only exists on /login).
        WebDriverWait(driver, 120).until(lambda d: d.current_url.rstrip("/") == BASE)
        session = driver.execute_script(
            "return fetch('/api/session', {method: 'POST'}).then("
            "function (r) { return r.status; })"
        )
        assert session == 200, f"session gate after passkey login: {session}"
        say("PASSKEY-E2E-DONE")
    except TimeoutException:
        say("PASSKEY-E2E-TIMEOUT")
        print(driver.page_source[:4000], file=sys.stderr, flush=True)
        raise
    finally:
        try:
            driver.quit()
        except Exception as exc:  # noqa: BLE001
            print(f"quit failed: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
