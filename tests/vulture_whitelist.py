"""Vulture whitelist: assignments that look unused but are load-bearing.

BuildFlow feeds every ``*.py`` file to vulture, so references here count
as usages. Every entry is an attribute assignment on a third-party
object whose value the underlying C library reads at runtime — deleting
the assignment changes behavior. Do not remove entries without checking
why they are listed.
"""

import ssl

from selenium.webdriver.chrome.options import Options as ChromeOptions

# Points the Selenium driver at the flake's chromium binary
# (tests/browser-e2e.py make_driver).
ChromeOptions.binary_location  # noqa: B018 - vulture whitelist reference

# tests/wsprobe.py deliberately trusts sofia's self-generated certificate:
# the probe verifies the transport path, not the PKI.
ssl.SSLContext.check_hostname  # noqa: B018 - vulture whitelist reference
ssl.SSLContext.verify_mode  # noqa: B018 - vulture whitelist reference
