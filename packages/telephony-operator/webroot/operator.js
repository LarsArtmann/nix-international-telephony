/* Operator window logic: fetch same-origin JSON (basic auth handled by
 * the browser's native prompt), render, auto-refresh. Read-only by
 * design — nothing here mutates PBX state. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // --- tabs -----------------------------------------------------------------
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      document
        .querySelectorAll(".tab")
        .forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      document.querySelectorAll(".panel").forEach((p) => (p.hidden = true));
      $(`tab-${tab.dataset.tab}`).hidden = false;
      if (tab.dataset.tab === "calls") refreshCdr();
      if (tab.dataset.tab === "sms") refreshSms();
      if (tab.dataset.tab === "health") refreshHealth();
    });
  });

  async function fetchJson(url) {
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (res.status === 401) {
      // The browser shows its native basic-auth prompt for this request.
      throw new Error("unauthorized (operator sign-in required)");
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
  }

  // --- CDR viewer -----------------------------------------------------------
  function directionClass(row) {
    if (row.context === "public") return "dir-in";
    if (row.accountcode) return "dir-out";
    return "dir-internal";
  }

  function renderCdr(entries) {
    const tbody = $("cdr-table").querySelector("tbody");
    if (!entries.length) {
      tbody.replaceChildren(
        Object.assign(document.createElement("tr"), {
          innerHTML: '<td colspan="7" class="empty">no call records yet</td>',
        }),
      );
      return;
    }
    tbody.replaceChildren(
      ...entries.map((row) => {
        const tr = document.createElement("tr");
        const cells = [
          [directionClass(row), row.context === "public" ? "in" : "out"],
          ["", row.caller_id_number || "—"],
          ["", row.destination_number],
          ["", row.start ? row.start.replace("T", " ") : "—"],
          ["num", String(row.billsec)],
          ["", row.hangup_cause],
        ];
        cells.forEach(([cls, text]) => {
          const td = document.createElement("td");
          if (cls) td.className = cls;
          td.textContent = text;
          tr.append(td);
        });
        const recTd = document.createElement("td");
        if (row.recording) {
          const a = document.createElement("a");
          a.className = "rec";
          a.href = row.recording;
          a.textContent = "listen";
          a.target = "_blank";
          a.rel = "noopener";
          recTd.append(a);
        } else {
          recTd.textContent = "—";
        }
        tr.append(recTd);
        return tr;
      }),
    );
  }

  async function refreshCdr() {
    const number = $("cdr-number").value.trim();
    const limit = $("cdr-limit").value;
    const params = new URLSearchParams({ limit, offset: cdrOffset });
    if (number) params.set("number", number);
    try {
      const data = await fetchJson(`/operator-api/cdr?${params}`);
      renderCdr(data.entries);
      $("cdr-newer").disabled = cdrOffset === 0;
      $("cdr-older").disabled = !data.more;
      const from = data.entries.length ? cdrOffset + 1 : 0;
      $("cdr-window").textContent = `${from}-${cdrOffset + data.entries.length}`;
      const exportParams = new URLSearchParams();
      if (number) exportParams.set("number", number);
      $("cdr-export").href = `/operator-api/cdr.csv?${exportParams}`;
    } catch (err) {
      renderCdr([]);
      console.error("cdr refresh failed:", err);
    }
  }

  // Paging walks in steps of the selected limit; filters restart at page 1.
  let cdrOffset = 0;
  const cdrStep = () => Number($("cdr-limit").value);
  $("cdr-newer").addEventListener("click", () => {
    cdrOffset = Math.max(0, cdrOffset - cdrStep());
    refreshCdr();
  });
  $("cdr-older").addEventListener("click", () => {
    cdrOffset += cdrStep();
    refreshCdr();
  });

  $("cdr-filter").addEventListener("submit", (event) => {
    event.preventDefault();
    cdrOffset = 0;
    refreshCdr();
  });

  let cdrTimer = null;
  $("cdr-auto").addEventListener("change", (event) => {
    clearInterval(cdrTimer);
    cdrTimer = null;
    if (event.target.checked) cdrTimer = setInterval(refreshCdr, 15000);
  });

  // --- SMS ------------------------------------------------------------------
  function renderSms(entries, unavailable) {
    const list = $("sms-list");
    if (unavailable) {
      list.replaceChildren(
        Object.assign(document.createElement("li"), {
          textContent: "no SMS store configured on this host",
        }),
      );
      return;
    }
    if (!entries.length) {
      list.replaceChildren(
        Object.assign(document.createElement("li"), {
          textContent: "no messages",
        }),
      );
      return;
    }
    list.replaceChildren(
      ...entries.map((msg) => {
        const li = document.createElement("li");
        const meta = document.createElement("div");
        meta.className = "meta";
        meta.textContent = `${msg.received_at} · ${msg.from} → ${msg.to}`;
        const body = document.createElement("div");
        body.textContent = msg.body;
        li.append(meta, body);
        return li;
      }),
    );
  }

  async function refreshSms() {
    try {
      const data = await fetchJson("/operator-api/sms");
      renderSms(data.entries, false);
    } catch (err) {
      renderSms([], true);
      console.error("sms refresh failed:", err);
    }
  }

  // --- Simulator --------------------------------------------------------------
  $("sim-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const dest = $("sim-dest").value.trim();
    const when = $("sim-when").value;
    const params = new URLSearchParams({ dest });
    if (when) params.set("when", when);
    const out = $("sim-out");
    out.hidden = false;
    out.textContent = "simulating …";
    try {
      const data = await fetchJson(`/operator-api/simulate?${params}`);
      out.textContent = formatSim(data);
    } catch (err) {
      out.textContent = `simulation failed: ${err.message}`;
    }
  });

  function formatSim(result) {
    const lines = [
      `call to ${result.destination} at ${result.time}`,
      ...result.matched_extensions.map((name) => `  extension ${name}`),
      ...result.trace.map(
        (entry) =>
          `  - ${entry.application} ${entry.data}${entry.note ? `  (${entry.note})` : ""}`,
      ),
    ];
    const outcome = result.outcome || {};
    if (outcome.type === "bridge") {
      for (const target of outcome.targets) {
        if (target.type === "extension")
          lines.push(`  => ring ${target.target}`);
        else if (target.type === "pstn")
          lines.push(`  => PSTN ${target.number} via ${target.gateway}`);
        else lines.push(`  => ${target.dial_string}`);
      }
    } else if (outcome.type === "voicemail") {
      lines.push(
        `  => voicemail (${outcome.mode}, box ${outcome.box ?? "n/a"})`,
      );
    } else if (outcome.type === "ivr") {
      lines.push(
        `  => IVR menu ${outcome.menu}${outcome.input ? ` (input ${outcome.input})` : ""}`,
      );
    } else if (outcome.type === "fax") {
      lines.push(`  => receive fax to ${outcome.file}`);
    } else {
      lines.push(`  => ${JSON.stringify(outcome)}`);
    }
    return lines.join("\n");
  }

  // --- Health -----------------------------------------------------------------
  function renderHealth(report) {
    const pill = $("health-pill");
    pill.dataset.state = report.ok ? "ok" : "degraded";
    pill.textContent = report.ok ? "healthy" : "degraded";
    const cards = $("health-cards");
    cards.replaceChildren(
      ...Object.entries(report.checks || {}).map(([name, check]) => {
        const card = document.createElement("div");
        card.className = "card";
        const h = document.createElement("h3");
        h.textContent = name;
        const state = document.createElement("div");
        state.className = `state ${check.state}`;
        state.textContent = check.state;
        card.append(h, state);
        const detail = check.profiles || check.gateways || check.units;
        if (detail) {
          const dl = document.createElement("dl");
          for (const [key, value] of Object.entries(detail)) {
            const dt = document.createElement("dt");
            dt.textContent = key;
            const dd = document.createElement("dd");
            dd.textContent = value;
            dl.append(dt, dd);
          }
          card.append(dl);
        }
        if (check.not_after) {
          const dl = document.createElement("dl");
          const dt = document.createElement("dt");
          dt.textContent = "expires";
          const dd = document.createElement("dd");
          dd.textContent = check.not_after;
          dl.append(dt, dd);
          card.append(dl);
        }
        if (check.error) {
          const p = document.createElement("p");
          p.className = "hint";
          p.textContent = check.error;
          card.append(p);
        }
        return card;
      }),
    );
  }

  async function refreshHealth() {
    try {
      renderHealth(await fetchJson("/operator-api/health"));
    } catch (err) {
      $("health-pill").dataset.state = "error";
      $("health-pill").textContent = "health unavailable";
      console.error("health refresh failed:", err);
    }
  }

  let healthTimer = null;
  $("health-auto").addEventListener("change", (event) => {
    clearInterval(healthTimer);
    healthTimer = null;
    if (event.target.checked) healthTimer = setInterval(refreshHealth, 15000);
  });

  // --- boot ---------------------------------------------------------------------
  refreshCdr();
  refreshHealth();
})();
