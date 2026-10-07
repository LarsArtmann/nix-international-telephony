"""Vulture whitelist: assignments that look unused but are load-bearing.

BuildFlow feeds every ``*.py`` file to vulture, so references here count
as usages. Entries are load-bearing definitions the repo's own tooling
consumes dynamically: attribute assignments whose value an underlying
library reads at runtime, and names the unittest loader instantiates by
discovery. Do not remove entries without checking why they are listed.
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

# http.server dispatches do_GET/do_POST by name and the socket machinery
# reads protocol_version/server_version/log_message — the subclass
# assignments are load-bearing even though no code in this repo calls
# them (api.py, telnyx-webhooks.py, tests/test_telnyx_bridge.py).
import http.server

http.server.BaseHTTPRequestHandler.do_GET  # type: ignore[attr-defined]  # noqa: B018  # dispatch entry point; typeshed omits it on the base
http.server.BaseHTTPRequestHandler.do_POST  # type: ignore[attr-defined]  # noqa: B018  # dispatch entry point; typeshed omits it on the base
http.server.BaseHTTPRequestHandler.do_DELETE  # type: ignore[attr-defined]  # noqa: B018  # subclasses define it; typeshed omits it on the base
http.server.BaseHTTPRequestHandler.log_message  # noqa: B018
http.server.BaseHTTPRequestHandler.protocol_version  # noqa: B018
http.server.BaseHTTPRequestHandler.server_version  # noqa: B018

# unittest discovers and instantiates TestCase subclasses by name, so
# vulture cannot see these e2e suites (tests/test_voice_agent_e2e.py)
# as used.
from tests.test_voice_agent_e2e import EndToEndCallSpec, EntrypointSpec

EndToEndCallSpec  # noqa: B018 - vulture whitelist reference
EntrypointSpec  # noqa: B018 - vulture whitelist reference
