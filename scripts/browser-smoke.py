#!/usr/bin/env python3
"""Post-deploy browser smoke: one real browser against a live vhost.

The curl lane (scripts/verify-live.sh) proves the HTTP surface; this
script proves the BROWSER surface a user actually gets — the anonymous
redirect to the single front door, the login page's DOM ids, and the
/config.js contract — with real chromium driven by selenium. Read-only
by design: no credentials are typed, no call is placed, nothing is
clicked that mutates state. Green here + green verify-live = the
deploy's user-facing shape is intact.

Run from any machine with the three deps (nothing else is needed):

    nix shell nixpkgs#python3Packages.selenium nixpkgs#chromium \\
        nixpkgs#chromedriver -- \\
        python3 scripts/browser-smoke.py https://pbx.example.com

Exit 0 = smoke green; 1 = a check failed (the failing check prints
first). Every check names itself so a red run reads like a triage list.
"""

import sys
import urllib.error
import urllib.request

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

# The /config.js keys a healthy deploy MUST serve (strict set — the
# same contract tests/configjs_check.py pins inside the VM).
CONFIG_KEYS = {
    "domain",
    "wsUrl",
    "turnServers",
    "phoneApi",
    "contacts",
    "agent",
    "asr",
}


def fail(name: str, detail: str) -> None:
    print(f"FAIL {name}: {detail}")
    raise SystemExit(1)


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
        raise SystemExit("usage: browser-smoke.py https://<domain>")
    base = sys.argv[1].rstrip("/")

    # /config.js: JSON, exact key set (no browser needed — but it is the
    # contract the island boots on, so it belongs in the same smoke).
    import json

    try:
        config = json.load(urllib.request.urlopen(base + "/config.js", timeout=10))  # nosec B310 - operator-supplied https URL
    except (urllib.error.URLError, json.JSONDecodeError) as err:
        fail("config.js", f"unreachable or not JSON: {err}")
    missing = CONFIG_KEYS - set(config)
    extra = set(config) - CONFIG_KEYS
    if missing or extra:
        fail("config.js keys", f"missing={sorted(missing)} extra={sorted(extra)}")

    options = ChromeOptions()
    options.binary_location = "chromium"
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.set_capability("acceptInsecureCerts", True)
    options.add_argument("--window-size=1280,900")
    service = Service(service_args=["--verbose"], log_output="/tmp/chromedriver-smoke.log")  # nosec B108 - operator log
    driver = webdriver.Chrome(service=service, options=options)
    try:
        # Anonymous root: the single front door (2.14.0+) redirects to
        # /login — staying on / would mean the session gate is broken.
        driver.get(base + "/")
        WebDriverWait(driver, 30).until(lambda d: d.current_url.rstrip("/") == base + "/login")
        print("PASS front door: anonymous / -> /login")

        email = driver.find_element(By.ID, "lp-email")
        button = driver.find_element(By.ID, "lp-login-btn")
        if email.tag_name != "input" or button.tag_name != "button":
            fail("login DOM", f"unexpected tags: {email.tag_name}/{button.tag_name}")
        print("PASS login DOM: #lp-email + #lp-login-btn present")
    finally:
        try:
            driver.quit()
        except Exception as exc:  # noqa: BLE001
            print(f"quit failed (harmless): {exc}", file=sys.stderr)

    print("SMOKE GREEN")


if __name__ == "__main__":
    main()
