# Status Report — 2026-10-25 12:44 CET

**Session scope:** OAuth support question → webphone flake consumption audit →
typed csrf wiring fix. This report covers ONLY this session's run and what it
touched. Point-in-time snapshot; annotate, never rewrite.

**Session timeline:** 12:15–12:44 CET. Working tree at start: clean at
`5d24191`. The auto-commit daemon landed this session's change as `974a03a`
(12:29:52).

---

## a) FULLY DONE

1. **OAuth support question answered with evidence.** Two surfaces exist:
   the webphone's own OIDC/SSO login (`services.telephony.webphone.oauth2`,
   options.nix — authorization-code + PKCE against the issuer, fail-closed
   assertions in default.nix, eval-proven by `oauth2Check` in tests/eval.nix)
   and the oauth2-proxy forward-auth gates for `/recordings/` and `/operator/`
   (tests/forward-auth.nix). An oauth2-only deployment (passkey OFF) is
   explicitly eval-proven. No code change needed.
2. **Webphone flake consumption audit completed.** Read the webphone repo's
   flake.nix, nix/packages.nix, nix/apps.nix, package/nixos-module.nix and
   package/options.nix against this repo's consumption points
   (flake.nix input + wrapper import, modules/telephony/web.nix,
   modules/telephony/default.nix). Verdict: near-perfect — module import
   single-sourced through the telephony wrapper, package defaulted with
   `mkDefault`, `nixpkgs` follows dedup, upstream Caddy vhost deliberately
   forced off with a legible eval assertion (upstream's own comment blesses
   the either/or), upstream dev-facing outputs (vulnix triage CLI, apps,
   checks, devshell) correctly NOT consumed.
3. **Lock freshness verified.** flake.lock pins webphone rev `50c4ac2`,
   identical to the local webphone checkout HEAD. No relock needed.
4. **Typed csrf wiring switch implemented, proven, committed.** Replaced the
   raw `settings.csrf.trusted_proxies/trusted_origins` writes in
   modules/telephony/web.nix with upstream's typed
   `services.webphone.csrf.trustedProxies/trustedOrigins` fronts (mkForce
   inside the upstream module — the documented API for a non-Caddy TLS
   proxy). Evidence: rendered settings byte-identical via
   `nix eval .#nixosConfigurations.pbx.config.services.webphone.settings.csrf`
   (`{"trusted_origins":["https://pbx.example.com"],"trusted_proxies":["127.0.0.1"]}`),
   `nix fmt` clean (0 changed), `checks.telephony-eval` build green,
   daemon commit `974a03a`. This closes backlog items #15
   (docs/status/2026-10-01_17-28_webphone-relock-execution-and-cdr-cancel-collision.md)
   and #18
   (docs/status/2026-10-02_11-06_buildflow-failures-relock-attribution-and-hook-gap.md).

## b) PARTIALLY DONE

1. **Typed csrf change: VM-layer proof not run.** Code + eval gate done;
   tests/webphone.nix pins the rendered csrf shape in-VM (its assertions
   read the live rendered config). Only eval-identity was proven this
   session. Remaining: run the telephony-webphone VM suite. Effort S
   (one command, 20–60 min wall clock). No blocker.
2. **CHANGELOG entry for the typed csrf switch not written.** The
   Unreleased section carries today's earlier auth-clobber fix but not this
   change. The daemon's heuristic commit message (`974a03a`) carries no
   attribution, so the CHANGELOG is the only place the why can live.
   Effort S. No blocker — same-edit-window bookkeeping was missed (see e).
3. **Verification-hygiene recovery incomplete by design.** The planned
   stash-based A/B probe for the eval warning was voided by the daemon
   commit; recovered via grep (tests/eval.nix passes `system =` to
   nixosSystem at four sites). The warning is pre-existing and unrelated;
   no fix attempted (out of session scope).

## c) NOT STARTED

1. **Full `nix flake check` after the change** — all VM suites realize; not
   run this session. Still wanted (CI runs it on push anyway).
2. **Cross-repo reference-consumer documentation** — the webphone repo's
   module comment says consumers "may import it or keep its own reverse
   proxy"; naming this stack as the reference import-consumer upstream is
   an unstarted, owner-gated idea (question 3).
3. **Telephony-wrapper passthroughs for upstream `serverTiming` /
   `websocket_path` options** — noticed during the audit, deliberately not
   started (no current operator need; YAGNI unless asked).

## d) TOTALLY FUCKED UP

1. **A verification step was theater, not verification.** The eval-gate
   command chained `nix run .#check-vm -- --help >/dev/null 2>&1` followed
   by an UNCONDITIONAL `echo "eval gate: OK"`. The `--help` flag is not a
   documented check-vm argument, its output was discarded, and the success
   echo fired regardless of that step's exit code. Nothing harmful executed
   (the command returned promptly) and the REAL gate —
   `nix build .#checks.x86_64-linux.telephony-eval` — did pass on the
   changed tree via the `&&` chain. Root cause: composing filler steps into
   a gate command. Lesson: every step in a verification chain must be able
   to fail loudly; no `/dev/null`, no unconditional success markers.
2. **A tree-mutating probe was designed against a daemon-shared tree.** The
   `git stash` A/B probe to prove the eval warning pre-existing failed with
   "No local changes to save" because the auto-commit daemon had already
   committed the change — exactly the race AGENTS.md documents. Recovered
   safely via read-only grep; no damage. Lesson: on this tree, probes must
   be read-only (grep / `git log -S`), never stash dances.

No user-facing surface broke; nothing lost data; both failures are process
failures, named so they stop recurring.

## e) WHAT WE SHOULD IMPROVE

1. **Gate-command composition.** Impact: a passing-looking gate can mask an
   unverified step (see d1). Fix: one concern per gate command; `&&`-chain
   only; any step whose failure should matter stays unredirected.
2. **Beat the daemon with same-window bookkeeping.** Impact: attribution
   (CHANGELOG why-lines) has to be reconstructed later, as now (b2). Fix:
   write the CHANGELOG entry in the SAME edit batch as the code change —
   the daemon commits within seconds and never carries the why.
3. **Read-only probing discipline on shared trees.** Impact: wasted probe
   - confusion (d2). Fix: grep and `git log -S` first; tree mutations only
     when uniquely authored.
4. **Skill loading before task tools worked well** (nix-review before the
   audit, status-report before this report) — keep the loop; noting it so
   the positive pattern is kept, not just the failures.

## f) Things we should get done next (session-derived, ranked)

| #  | Task                                                                                                                          | Impact | Effort | Category      |
| -- | ----------------------------------------------------------------------------------------------------------------------------- | ------ | ------ | ------------- |
| 1  | Run `nix run .#check-vm -- telephony-webphone` to VM-prove the typed csrf rendered shape                                      | High   | S      | Quality       |
| 2  | Add CHANGELOG Unreleased entry for the typed csrf switch (why + rendered-identity proof)                                      | High   | S      | Documentation |
| 3  | Full `nix flake check` to realize all VM suites post-change                                                                   | High   | M      | Quality       |
| 4  | Add an eval-time csrf check to tests/eval.nix pinning typed fronts → rendered keys (today only the VM suite pins it)          | Medium | S      | Quality       |
| 5  | Verify docs/ops-runbook.md documents the oauth2/OIDC deployment recipe beside "Passkey surfaces" (or add it)                  | Medium | S      | Documentation |
| 6  | Silence or modernize the pre-existing `'system' has been renamed` eval warnings (tests/eval.nix, four `system =` sites)       | Low    | S      | Cleanup       |
| 7  | Sweep live docs for any remaining claims that the stack writes raw `settings.csrf.*` (archived snapshots stay untouched)      | Low    | S      | Cleanup       |
| 8  | Decide + wire `serverTiming` passthrough option in the telephony wrapper if diagnostics are ever wanted on the live host      | Low    | S      | Feature       |
| 9  | Upstream: name this stack as reference import-consumer in the webphone repo's module comment/README (owner-gated, question 3) | Low    | M      | Documentation |
| 10 | HARVEST this report's §f into TODO_LIST.md per docs-health (pending owner instruction; this session was told to wait)         | Medium | S      | Documentation |

Session-scoped honesty over padding: ten concrete items, not fifty. Nothing
else observed this session justifies a queue entry; bulk brainstorming
belongs to ROADMAP, not a manufactured list.

## g) Questions I can NOT figure out myself

1. **History hygiene for `974a03a`:** the daemon's heuristic message carries
   the typed-csrf change and may already be pushed (the daemon pushes).
   Rebase-re-author it with a proper message (history-rewrite risk on a
   shared remote), or leave history as-is and let the CHANGELOG entry (f2)
   carry attribution? My lean: leave it, CHANGELOG carries the why — but
   the push state is unknowable from here without fetching, and the
   rebase-vs-leave call is yours.
2. **Close the VM-proof loop now?** Run the telephony-webphone suite
   (20–60 min) this session to VM-prove the csrf shape, or accept the
   eval-identity proof and let CI's `nix flake check` cover it on push?
3. **Cross-repo visibility:** want the webphone repo to document this stack
   as its reference consumer (an upstream PR touching its README/module
   comment), or should cross-repo references stay one-directional (this
   repo only)?

---

_Report written by Crush (glm-5.3) at operator demand; .md format is an
explicit operator override of this report type's HTML-canonical default._
