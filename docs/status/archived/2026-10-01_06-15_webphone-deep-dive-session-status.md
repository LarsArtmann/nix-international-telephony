# Status: webphone deep-dive audit session — 2026-10-01 06:15

Scope: THIS session only — the `library-deep-dive` audit of the webphone
flake input ("Are we using ~/projects/webphone (latest) to the max?"),
its deliverable, and this self-review. Nothing else researched.

Deliverable of the session: `docs/research/2026-10-01_webphone-deep-dive.html`
(commit `40131d1`; a daemon race also landed a partial intermediate in
`1e552f4` — see d)1). Verdict delivered: adoption 78/100, 17/24
capabilities fully leveraged, 0 anti-patterns, 4 missed opportunities,
lock 20 commits behind upstream main.

---

## a) FULLY DONE

~~1. **Skill protocol followed end-to-end**: loaded `library-deep-dive`~~ done at 40131d1
   SKILL.md first, executed all 7 phases (discovery → capability research
   → gap analysis → scoring → HTML report → cross-references → git).
~~2. **Usage baseline (Phase 1)** with file-level citations: flake.nix~~ done at 40131d1
   module wrapper (lines 61-71), web.nix settings wiring, messaging /
   fax-feed / monitoring integration points, both example hosts, the
   test contract (tests/webphone.nix, backup.nix, common.nix).
~~3. **Capability research (Phase 2)** from the upstream working tree at~~ done at 40131d1
   HEAD AND verified against the pinned rev via `git show`: option
   surface (package/options.nix + nixos-module.nix), full config key
   surface (internal/config/config.go), HTTP surface (server.go routes,
   metrics.go payload), CHANGELOG state.
~~4. **Version currency quantified**: pin `4266b8d` (2026-09-30) vs~~ done: report plus the def576a addendum pin the currency trail (4266b8d → f706575)
   upstream main `31c9f97` (2026-10-01) = 20 commits, all post-v2.8.0
   unreleased; module-surface equality at the pin PROVEN (options lived
   inline in nixos-module.nix at the pin; package/options.nix was created
   at in-range commit `383b711` — I caught and resolved my own misleading
   first read of the diff instead of shipping it).
~~5. **Gap analysis + scoring**: 4 missed opportunities (backup coverage,~~ done at 40131d1
   /metrics exposed-but-unconsumed, identities, webhook_secret_file), 3
   partials (gateway seam, version currency, memoryMax), N/A set
   explicitly justified; every finding cites code in this repo or upstream.
~~6. **Report written and structurally validated**: HTML tag balance checked~~ done at 40131d1
   programmatically (HTMLParser, zero mismatches); template CSS copied
   from the kit file, never retyped.
~~7. **Committed** `40131d1` with a detailed, findings-summarizing message;~~ done at 40131d1
   not pushed.
~~8. **Post-hoc verifications (done during THIS self-review, see also d)3)**:~~ done: AGENTS.md now records v2.8.0 tagged 2026-09-30 (the stale v2.6.0 note is gone)
   - "v2.8.0 = latest tag" — **CORRECT** (`git tag --sort=-creatordate`
     shows v2.8.0 on top). Incidental finding: AGENTS.md's "upstream tags
     trail the version literal (tags stop at v2.6.0)" is now STALE.
   - Treefmt/prettier `includes` is scoped to
     `packages/telephony-operator/webroot/*` only → the new
     `docs/research/*.html` is NOT format-gated; commit `40131d1` cannot
     redden `checks.format`.

## b) PARTIALLY DONE

~~1. **Report rendering verification**: tag balance validated, but I never~~ → routed to TODO_LIST (browser-render deep-dive report)
   rendered it in a browser nor verified every CSS class I used
   (`.tag.amber`, `.hero-shapes`, `.strengths/.check`, `.compare`,
   `.highlight`, `.num`, `.footer`) exists in the template. High
   confidence (all copied from template/output-guide), zero proof.
~~2. **Recommendation snippets**: every option name was checked against the~~ done: all three snippets landed real and eval/test-covered — identitiesCheck (tests/eval.nix), /metrics fence asserts (tests/webphone.nix), backup canaries (tests/backup.nix)
   real upstream options (`retentionDays`, `webhook_secret_file`,
   `cfg.messaging.port`), but the snippets were never eval-tested —
   notably `identities = lib.mapAttrs (_: g: g.did) cfg.gateways` uses an
   attr path (`cfg.gateways`) I did not verify, and the nginx `/metrics`
   fence is illustrative only. The repo has a cheap eval-check pattern
   (tests/eval.nix) that would have proven them.
~~3. **Methodology transparency**: sources and revs cited, but (i) the~~ done at def576a
   Context7/agentic_fetch deviation (tools absent in this harness;
   substituted local checkout + git + gh) is only implied, and (ii) the
   78/100 score has no published weighting — the capability matrix groups
   rows, so a reader cannot recount the 24 from the report alone.
~~4. **Feature delta of the 20-commit gap**: enumerated from commit~~ done at def576a
   subjects, not from the full Unreleased CHANGELOG diff — auto-commit
   squashes could hide items.

## c) NOT STARTED

(The audit was read-only by design; none of its findings were executed.)

~~1. Webphone data backup: `services.webphone.backup.enable` + webphone~~ done at e4e0f45
   snapshot dir in the restic paths (+ backup VM-test round-trip).
~~2. `/metrics` decision: fence (allow 127.0.0.1, deny all) or wire a~~ done at d8feffd
   consumer.
~~3. Relock webphone `4266b8d` → `31c9f97` via the documented lock-bump~~ superseded by the attributed relock train (d8bd34c f706575 → … → 36f0c6f4, CHANGELOG)
   ritual.
~~4. `settings.identities` derivation from gateways/DIDs (+ facade option).~~ done at cae905e
~~5. Gateway auto-wiring (`mode = "webhook"`, `webhook_url`,~~ done at cae905e
   `webhook_secret_file`) when `messaging.enable`.
~~6. `memoryMax` in the pbx-prod template.~~ done at 055f78a
~~7. TODO_LIST harvest of the audit findings (status-report skill HARVEST~~ done at 19610ea
   step — pending deliberately because the user said WAIT).

## d) TOTALLY FUCKED UP

~~1. **Daemon race on a half-written artifact**: I created the report~~ done at 1cc0d3e
   head-only (sed splice into `docs/research/`) and appended the body
   only afterwards — the auto-commit daemon committed the 849-line
   fragment in between (`1e552f4`). Final state at HEAD is complete and
   correct, but history carries a broken intermediate. I KNEW the daemon
   exists (AGENTS.md, checked lanes at session start) and still handed it
   a window. Fix pattern: assemble in /tmp, `mv` in atomically.
~~2. **Unverified claim written against recorded knowledge**: the scorecard~~ done: claim vindicated and the AGENTS.md tag note corrected (v2.8.0 tagged 2026-09-30)
   asserts "0 releases behind (v2.8.0 = latest tag)" — written WITHOUT
   checking, while project AGENTS.md recorded the opposite ("tags stop at
   v2.6.0"). Verification (in this review) shows I was right and
   AGENTS.md is stale — but the process failure stands: I asserted
   upstream state that contradicted session-loaded knowledge without a
   5-second `git tag`. That is exactly the verify-external-claims class
   this setup has skills for.
~~3. **Verification order inverted**: the treefmt-scope check and the tag~~ done: both deferred checks passed (self-recorded, no damage); the tag-fact residue landed in AGENTS.md
   check both happened AFTER the commit, during this self-review. Both
   passed, so no damage — but the correct order is check-then-commit;
   this time it was luck, not discipline.

## e) WHAT WE SHOULD IMPROVE

~~1. Atomic artifact assembly under the auto-commit daemon (tmpfile → mv).~~ done at 1cc0d3e
~~2. Gate-adjacent pre-commit checks for non-code artifacts: does the new~~ → routed to TODO_LIST (non-code artifact gate check)
   file fall under treefmt/prettier includes? Do its claims contradict
   AGENTS.md? Both are one-liners I only ran retrospectively.
~~3. Eval-test (or explicitly label as unvalidated) every code snippet in~~ done: identities eval-armed (tests/eval.nix); fence asserted (tests/webphone.nix); backup block real (tests/backup.nix)
   research deliverables — the repo's eval-check pattern makes this cheap.
~~4. Publish the score weighting (or the raw capability enumeration) in~~ done at def576a
   audit reports so numbers are recountable.
~~5. HARVEST discipline: an audit's findings belong in TODO_LIST in the~~ done at 19610ea
   SAME session, not entombed in a timestamped file.
~~6. Memory maintenance found stale: AGENTS.md webphone tag note needs the~~ done: AGENTS.md records v2.8.0 tagged 2026-09-30
   v2.8.0 reality (and this session's "module options relocated to
   package/options.nix, consumer-transparent" context if durable).
~~7. Convert code-reasoned exposure claims into probe evidence where cheap~~ done at e0eafa1
   (demo VM curl for /metrics) — "exposed to the internet" deserves a
   probe before it drives a security-adjacent recommendation.
~~8. Cite upstream module-check tests (nix/module-check-backup.nix,~~ done at def576a
   module-check-csrf.nix) as evidence when recommending those features —
   they pin the exact behaviors I recommended.

## f) Up to 50 things to get done next

(Real items only — 28; no padding. 1-8 are the audit's ranked
opportunities, 9+ are session-hygiene and evidence-hardening.)

~~1. Enable `services.webphone.backup` (retentionDays = 30) + add the~~ done at e4e0f45
   snapshot dir to restic `backups.paths` in pbx-prod.
~~2. Extend tests/backup.nix with a webphone-data canary round-trip~~ done: tests/backup.nix webphone snapshot canaries round-trip
   (message/fax blob survives restore).
~~3. Decide + implement `/metrics`: nginx fence (allow 127.0.0.1, deny all)~~ done at d8feffd
   — minimum viable fix for an internet-exposed, unconsumed surface.
~~4. Optional consumer for /metrics: operator health card (build_info,~~ → routed to TODO_LIST (metrics consumer card)
   uptime, counts) behind the existing basic-auth realm.
~~5. VM assertion that /metrics is fenced (curl from outside → 403).~~ done: tests/webphone.nix asserts egress 403 + loopback scrape
~~6. Relock webphone to `31c9f97` following docs/ops-runbook.md~~ superseded by the attributed relock train (CHANGELOG 2026-10-01 → 11-06)
   "Lock-bump runbook" (binary build, fast gates, webphone suites,
   browser E2E, HAND-AUTHORED commit naming revs).
~~7. Derive `settings.identities` from `gateways.<name>.did` in web.nix~~ done at cae905e
   (verify the attr path first) + config.js assertion in tests/webphone.nix.
~~8. Auto-wire `gateway.{mode,webhook_url,webhook_secret_file}` in~~ done at cae905e
   messaging.nix when `cfg.messaging.enable`; delete the pbx-prod CHANGEME
   block for it.
~~9. `services.webphone.memoryMax = "512M"` in hosts/pbx-prod.~~ done at 055f78a
~~10. Facade options (policy-gated): `webphone.retentionDays`,~~ done: webphone.timezone facade landed (CHANGELOG 2026-10-25 wall-clock ownership); retentionDays facade stays owner-gated (routed to TODO_LIST)
    `webphone.timezone`.
~~11. Evaluate `/health` dashboard mount vs the stack's own operator window~~ done at e0eafa1
    (fence first if ever enabled).
~~12. HARVEST this report's (f) into TODO_LIST.md via docs-health.~~ done at 19610ea
~~13. Update AGENTS.md: webphone tags no longer stop at v2.6.0 (v2.8.0~~ done: AGENTS.md records v2.8.0 tagged 2026-09-30
    tagged 2026-09-30).
~~14. Annotate the research report with the verified tag fact + correction~~ done at def576a
    note for the previously unverified claim (append, never rewrite).
~~15. Browser-render the research report (screenshot) to close the CSS-class~~ → routed to TODO_LIST (browser-render deep-dive report)
    verification gap.
~~16. Eval-test the three report snippets (identities mapAttrs, nginx fence,~~ done: identities eval-armed; fence + backup test-covered; the addendum labels the illustrative remainder (def576a)
    backup block) or mark them "illustrative, unvalidated".
~~17. Read the full Unreleased CHANGELOG diff `4266b8d..31c9f97` for a~~ done at def576a
    complete feature delta; update the report's version table if needed.
~~18. Probe /metrics on the demo VM (`nix run .#vm`) to convert the~~ done at e0eafa1
    exposure claim to probe evidence.
~~19. Cite upstream nix/module-check-backup.nix + module-check-csrf.nix in~~ done at def576a
    the report appendix.
~~20. Show the adoption-score weighting / raw 24-capability enumeration in~~ done at def576a
    the report appendix.
~~21. Consider a TODO_LIST row per audit finding (done via 12).~~ done at 19610ea
~~22. Record the daemon-race lesson (atomic assembly) where the other~~ done at 1cc0d3e
    daemon lessons live (docs/lessons/operating.md candidate).
~~23. Consider fencing ALL open-subrouter operator endpoints (/livez,~~ done at e0eafa1
    /startupz, /healthz ride the catch-all too — /healthz is intentionally
    used by telephony-health from loopback only; evaluate each).
~~24. If a data-minimization policy ever applies: retention_days wiring +~~ → routed to TODO_LIST (retentionDays policy wiring)
    consent notes for messages like the recordings one in pbx-prod.
~~25. Watch for upstream v2.9.0 cut (announcement drafts exist for v2.8.0;~~ superseded by the relock train — the pin long since passed the v2.9.0 seed
    the 20 commits are the v2.9.0 seed) — relock target may move.
~~26. Optional: `serverTiming.enable` behind a debug flag for perf triage~~ → routed to TODO_LIST (serverTiming debug flag)
    sessions only.
~~27. Consider facade exposure for paperless (fax archive) if a Paperless-ngx~~ NOT-DO — condition never triggered; no Paperless-ngx exists in this stack (no modules/hosts references)
    instance ever enters the picture.
~~28. Session convention: run `date` + lane detection at session START too~~ done: AGENTS session-start convention (git status + ps aux; detect lanes before editing)
    (I ran lane detection but never anchored a timestamp until asked).

## g) Questions I cannot figure out myself

~~1. **Execute or park?** Should I now implement the top-3 opportunities~~ done: executed the same day — T01-T06 landed, T07 relocked (d8bd34c), T09-T11 verdicted (e0eafa1)
   (backup wiring + restic path, /metrics fence, relock to `31c9f97`),
   or park everything in TODO_LIST for a planned train? (Owner-priority
   call; the relock in particular owns a ritual cost.)
~~2. **/metrics end-state**: fence-only (loopback scrape) or do you want a~~ done: fence-only for now — fence landed (d8feffd); consumer routed to TODO_LIST
   consumer (operator card / future Prometheus)? This decides items 3-5.
~~3. **Relock timing**: ride main now (`31c9f97`, module surface proven~~ done: rides main — repeated attributed relocks since (CHANGELOG 2026-10-01 → 11-06)
   identical) or wait for an upstream v2.9.0 tag so the lock always sits
   on a tagged rev? (Current owner decision on record is "tracks main",
   so this is really: is a day-old main acceptable mid-train?)

---

_Point-in-time snapshot. Annotate, never rewrite. Generated by the
status-report + brutal-self-review skills at the user's explicit request
(Markdown format overriding the skill's HTML default per instruction)._
