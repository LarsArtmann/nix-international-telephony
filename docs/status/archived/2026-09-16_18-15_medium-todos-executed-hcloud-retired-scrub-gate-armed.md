# Status Report — Medium TODO Rows Executed: hcloud.tf Retired, Scrub Gate Armed

**Point-in-time snapshot: 2026-09-16 18:15 CEST.** Scope: this session only —
executing the two Medium-impact TODO_LIST rows the owner pasted
(`infra/hcloud.tf` reconcile; fill `secrets/scrub-patterns.txt`), plus the
self-review the owner asked for. Nothing else was touched; the fspbx trial,
console concept, and deployment-runbook threads from the 18:00 reports are
referenced but not advanced.

Skill-format overrides (user-mandated, standing since the 16:43 report):
`.md` instead of HTML, self-review folded in, no manual commit (daemon owns
them).

## a) FULLY DONE (this session, each with its verification)

1. **`infra/hcloud.tf` retired** (the TODO offered import-or-retire; import
   was unexecutable — no Hetzner token exists locally, no server IDs staged,
   and crucially **no Terraform state ever existed**: `terraform init` ran
   once (2026-08-29, OpenTofu provider cache found) but no apply ever
   happened, so the module described a third server nobody has). Tracked
   files removed via `git rm`; untracked `.terraform/` provider cache and
   lock file moved to trash; empty dir dropped. Decision + rationale
   recorded in three homes: CHANGELOG `### Removed`, the planning doc's M5.4
   inline `→ 2026-09-16: RETIRED` marker (the plan explicitly asked for the
   decision recorded inline), and `docs/deploy.md` §4 rewritten from
   "create the VM (e.g. `infra/hcloud.tf` — Terraform)" to the real path
   (Hetzner console/API + cloud-init user-data installing the key, cf. the
   private flake's `cloud-init.yaml`).
2. **`secrets/scrub-patterns.txt` filled with real values** — 23 patterns
   (verified by the gate's own count): both DIDs in 7/5 spellings, the
   personal mobile in 5, the Telnyx SIP username, its password (appended
   via shell so it never appeared in any tool output), the API-key prefix,
   and three Hetzner addresses (current server, old server, dead /64
   prefix). File is gitignored (proven: `git check-ignore`) and mode 600.
   Owner-only gaps (DE mobile, ssh fingerprints, new /64) are marked
   placeholders inside the file.
3. **The gate bit, and the tree was scrubbed** — exactly the tripwire's
   purpose. 13 value occurrences redacted across the 2026-09-02 and
   2026-09-03 status reports, annotation-style (`[redacted 2026-09-16]`,
   plus a header blockquote explaining where values live). Notably includes
   the **spaced US-DID spelling at 09-02 line 17 that the 2026-09-03
   redaction pass missed** (that pass's `-S` scan evidently searched only
   the digit-only spelling) — the spelling-variant failure mode is why the
   patterns file demands every spelling. This executes 09-03 §f.16 exactly
   as scripted there, i.e. §g.2 **option A** (follow-up scrub commit;
   history keeps the values) — consistent with the owner's standing
   09-03 decision to accept pushed history. §f.16 and §g.2 now carry
   inline `→ 2026-09-16` resolution markers.
4. **History exposure quantified** (report-only, no surgery):
   `scripts/scrub-check.sh --history` finds 8 pattern groups across **3
   already-pushed commits** (`bc87d7c`, `feadbae`, `94ae5c1`) — mobile,
   Warsaw DID, US-DID spaced form, old IPv4/IPv6. The NEW values (current
   server IP, SIP credential, key prefix) have zero history hits — the
   09-03 purge holds for them. Parked as a new BLOCKED TODO row with the
   commit list and the `--history --strict` precondition.
5. **Gates green after everything**: `scrub-check` OK (23 patterns, tree),
   `tests/drift_alarm.py` PASS, `pre-commit run --all-files` all six hooks
   Passed (changelog-headings, deadnix, gitleaks, nixfmt, scrub-check,
   statix). All changes landed via three daemon auto-commits (`51dc0fe`
   latest); scrub-check re-run green post-commit.

## b) PARTIALLY DONE

- **Delivery to origin**: every change is local-only. → done — the daemon recovered 19:08; origin == main, CI green The daemon's push
  loop was already stalled at 18:00 (23+ commits ahead); now more. Origin
  CI has not seen any of this. Not mine to push without an explicit ask.
- **Scrub coverage**: the file holds every value discoverable from local
  sources; the three owner-owned placeholders remain unfilled (see g.3). → open — owner (fill or delete the placeholder block)
- **Full `nix flake check` not run locally** (now run — green 18:01, and CI green since): I reasoned the diff is
  docs-only plus deletion of a directory nothing references (grepped
  tracked tree; flake.nix never touched `infra/`). Sound, but reasoned —
  CI will be the first actual full run on this diff.

## c) NOT STARTED (session scope)

- The history-rewrite half of §g.2 (owner decision, now a BLOCKED row).
- The 18:00 reports' own next-things (fspbx trial verdict items, console
  collapse, TODO/ROADMAP harvest from those reports) — deliberately
  untouched; this session was the two pasted rows.

## d) TOTALLY FUCKED UP (owned, with root causes)

1. **Off-by-one claim in my end-of-session summary**: I wrote "14 value
   occurrences redacted"; the true count is 13 (6 in 09-02, 7 in 09-03).
   Never re-verified the number before publishing it. Small, but exactly
   the "did I lie" discipline this repo holds — counts are claims too.
2. **Misread tool output → failed command**: my first `git rm` included
   `infra/.terraform.lock.hcl`, which was untracked (ignored by
   `infra/.gitignore`) — I had conflated `ls` output with `git ls-files`
   output when inventorying. Cost: one aborted command. Root cause:
   skimming mixed-output blocks instead of reading them.
3. **Two read-before-edit rejections**: edited the planning doc and the
   09-03 report having only grepped them, never Viewed. The tool stopped
   me both times; cost: two round trips. The rule exists precisely for
   this.
4. **Dismissed an error line in gate output**: `pre-commit run` printed
   `[ERROR] Cowardly refusing to install hooks with core.hooksPath set`
   before running the hooks. I labeled it "informational" and moved on
   without investigating. The hooks demonstrably ran (six Passed lines),
   so verification stands — but WHO sets `core.hooksPath`, and whether it
   shadows `.git/hooks/pre-commit` for the daemon's plain `git commit`s,
   is unknown and unflagged anywhere. Same family as "theorize past the
   data": an unexplained error treated as noise.

## e) WHAT WE SHOULD IMPROVE

- **Verify counts before summarizing** — derive from the diff, don't
  estimate (d.1).
- **Never label an error line "informational" without one minute of
  investigation** — `git config --get core.hooksPath` would have answered
  it on the spot (d.4).
- **When substituting a nix check with a direct script run, prove
  equivalence**: I ran `tests/drift_alarm.py TODO_LIST.md FEATURES.md`
  instead of building `checks.docs-drift`; I did not read how the check
  invokes the script (args could differ). Probably identical, unproven.
- **Read-before-edit is not optional**, even for one-line table edits (d.3).
- **Pre-existing doc-drift observed**: the TODO row's evidence said the
  gate "runs warning-only until real patterns exist", but the file already
  existed with a dummy placeholder (`zzz-no-such-value-anywhere-98765`) —
  the row's evidence was stale before I started. Status claims in TODO
  rows rot the same way status reports do.

## f) NEXT (ranked, realistic — not padded)

1. Owner: history-rewrite decision for the 3 pushed commits (BLOCKED row; → done — option B executed: history rewritten (d7ac48f), 0 pickaxe hits on origin
   `--history --strict` first if taken).
2. Owner: push local main (or restart the daemon's push loop); then → done — recovered 19:08
   confirm origin CI green on the new head.
3. Investigate `core.hooksPath`: who sets it, and does it bypass the → open — TODO_LIST row (core.hooksPath investigation)
   git-hooks.nix-installed `.git/hooks/pre-commit` for daemon commits?
4. Prove `checks.docs-drift` ≡ my direct `drift_alarm.py` run (read its → done — drift_alarm.py extended + the check gate runs it (2026-09-16 docs-health round)
   wiring in flake.nix / build the check — cheap, no VM).
5. Owner: fill the three marked pattern placeholders (DE mobile, ssh → open — owner (three pattern placeholders)
   fingerprints, new /64) — or declare them out of scope and delete the
   placeholder block.
6. Full local `nix flake check` before the next release/tag (CI carries → done — 18:01
   this diff until then).
7. Existing Critical row: rescue-boot + reinstall + first calls runbook. → open — deploy lane §P1 (TODO_LIST)
8. Existing BLOCKED rows: Warsaw DID re-purchase + KYC window; Telnyx API → standing — TODO_LIST blocked rows
   key rotation (note: rotation changes the `KEY…` prefix pattern in the
   patterns file — update it in the same action).
9. Recording-consent posture decision (gates first real traffic). → answered 2026-09-16 — record ALL calls, consent accepted
10. fspbx trial verdict items (18:00 report f.1–f.14) — owner click-through → done — P7 closed with evidence; verdict sign-off = TODO_LIST blocked row
    first; everything else there hangs off that verdict.
11. Delete the old billing server once the new one is proven (money leak; → open — deploy lane §P5.3 (owner)
    also retires two of the 23 patterns — old IPv4 and dead /64).
12. Idea (optional): a warning-only periodic `scrub-check --history` job so → open — ROADMAP theme 5 (warning-only periodic history scrub idea)
    history drift is visible without failing CI on today's known hits.

## g) QUESTIONS FOR THE OWNER (cannot be figured out from here)

1. **The pushed-history leak (09-03 §g.2, now concrete)**: 3 pushed → done — rewrite executed (d7ac48f)
   commits carry the personal mobile, both DIDs, and the old server
   addresses. Rewrite + force-push (removes them; nobody depends on this
   history yet), or accept the exposure as you did on 09-03?
2. **May I push local main?** The daemon's loop is stalled and origin CI → done — recovered 19:08
   is red on stale code while every local suite is green — same question
   as the 18:00 report, still unanswered.
3. **The three pattern placeholders** (German mobile, ssh key → open — owner (fill placeholders or delete the block)
   fingerprints, the new server's /64): should they be protected values
   (you fill them), or out of scope (I delete the placeholder block)?

— END OF REPORT. Waiting for instructions.
