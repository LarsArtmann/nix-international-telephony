# Browser E2E: two headless chromium instances (fake media) register as
# extensions 1000 and 1001 through the nginx wss://pbx.test/sip proxy and
# complete a real 1000 -> 1001 WebRTC call (DTLS-SRTP), then hang up.
#
# Driven by Selenium; the NixOS testScript (tests/browser.nix) polls this
# script's stdout markers and asserts the call server-side via fs_cli.
import sys
import time

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

CHROMEDRIVER = "@chromedriver@"
CHROMIUM = "@chromium@"
PASSWORDS = {"1000": "test-1000-x9y8z7", "1001": "test-1001-u6t5s4"}


def make_driver():
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
    # Let the remote <audio> element play without a user gesture.
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    options.add_argument("--window-size=1280,900")
    service = Service(executable_path=CHROMEDRIVER)
    return webdriver.Chrome(service=service, options=options)


def wait_text(driver, selector, substring, timeout=180):
    WebDriverWait(driver, timeout).until(
        lambda d: substring in d.find_element(By.CSS_SELECTOR, selector).text
    )


def login(driver, extension):
    driver.get("https://pbx.test/")
    WebDriverWait(driver, 180).until(
        EC.presence_of_element_located((By.ID, "login-form"))
    )
    driver.find_element(By.ID, "ext").send_keys(extension)
    driver.find_element(By.ID, "pass").send_keys(PASSWORDS[extension])
    driver.find_element(By.ID, "login-form").submit()
    wait_text(driver, "#reg-status", "registered")
    print(f"{extension}-REGISTERED", flush=True)


def main():
    caller = make_driver()
    callee = make_driver()
    try:
        login(caller, "1000")
        login(callee, "1001")

        # Dial 1001 from 1000; the callee banner must name the caller.
        caller.find_element(By.ID, "dest").send_keys("1001")
        caller.find_element(By.ID, "dial-form").submit()
        wait_text(callee, "#incoming-from", "1000")
        print("INCOMING-SHOWN", flush=True)

        callee.find_element(By.ID, "accept-btn").click()
        wait_text(caller, ".call-state-text", "in call")
        wait_text(callee, ".call-state-text", "in call")
        print("CALL-ESTABLISHED", flush=True)

        # Keep the call up while the testScript asserts the bridge and
        # media server-side (fs_cli show channels / detailed_calls).
        time.sleep(15)

        caller.find_element(By.CSS_SELECTOR, ".hangup-btn").click()
        WebDriverWait(caller, 120).until(
            lambda d: not d.find_elements(By.CSS_SELECTOR, ".call-card")
        )
        WebDriverWait(callee, 120).until(
            lambda d: not d.find_elements(By.CSS_SELECTOR, ".call-card")
        )
        print("E2E-OK", flush=True)
    finally:
        for driver in (caller, callee):
            try:
                driver.quit()
            except Exception as exc:  # noqa: BLE001 - best-effort cleanup
                print(f"quit failed: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
