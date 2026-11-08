# mkForce audit train — 19 sites reviewed, 14 load-bearing, one inert block deleted, one trap caught live

**Session:** 2026-11-08, ~16:00–17:15 CET (single session, task: "review
ALL `lib.mkForce` usages, document why each is needed and how we could do
better"). Continues the 08:44 and 15:45 trains' day. Everything landed
through the auto-commit daemon across 9 heuristic commits
(`080e5cb` → `1f348c8`); the working tree is clean and the final live
count was re-verified against HEAD. §g has three owner-only questions.

## a) FULLY DONE

1. **Full inventory, every site read in context, every conflict source
   verified against the pinned upstream sources.** 19 live `mkForce`
   sites across 6 files (secrets.nix ×4, eval.nix ×5, prod-boot.nix ×6,
   pbx.nix ×2, web.nix ×1, metal-boot.nix ×1; the other 23 grep hits
   are docs/CHANGELOG snapshots). Upstream ground truth fetched at the
   locked revs: nixpkgs `f9a75f41` (freeswitch module sets
   `CPUSchedulingPolicy = "fifo"` and the `-conf ${configPath}`
   ExecStart as PLAIN defs; qemu-vm.nix overrides `fileSystems` at
   `mkVMOverride` priority 10 and builds `qemu.drives` as a mkMerge of
   plain lists; grub's device→devices mirror) and webphone `e762f5af`
   (typed csrf fronts are the documented precedence API; caddy.enable
   gates its generator, no auto-enable).
2. **The precedence model corrected and PROVEN, not theorized.** At each
   option node the lowest-priority definition group wins and higher
   defs are discarded entirely; list options concat same-priority defs
   instead of conflicting; attrsOf `mkForce {}` DOES erase sibling
   leaves; `mkVMOverride` (10) beats `mkForce` (50). Encoded in
   AGENTS.md's gotcha bullet.
3. **A reusable eval-only precedence probe built** (testing-python.nix
   `evalTest` → `.config.nodes.machine` — machine IS the config): the
   decisive verdicts took seconds instead of VM runs. Recipe + all four
   gotchas documented in the audit doc (§Probe recipe).
4. **Inert config deleted with byte-identical proof.** prod-boot.nix's
   forced `fileSystems."/"` block NEVER took effect (framework priority
   10 wins; the machine always booted `/dev/disk/by-label/nixos`) —
   deleted; evalTest probe A/B byte-identical before/after; check
   instantiation clean (`qns4x48gz5r78zdv4ghsv99h9ddns18y`).
5. **Three decorative forces normalized to plain assignments** (eval.nix
   crmEval/turnFileEval/negative-turn-arm `authSecret` — none had a
   competing definition; now consistent with the other three
   exactly-one-of negative arms). Proof: telephony-eval resolved to the
   byte-identical drv `1j9psf51479vnc9vdpxd3clnmyzdpc0j`
   (`--no-eval-cache` re-instantiation + `--rebuild` output
   verification, exit 0) — verdicts unchanged by construction.
6. **The grub.devices trap caught live and documented.** Normalizing
   prod-boot's `grub.devices` to a plain assignment made the A/B probe
   show TWO boot devices (`/dev/vda` + the by-id mirror concat) —
   reverted within minutes, byte-identical re-proven
   (`PROBE_AB_IDENTICAL_AFTER_REVERT`), and the line now carries a
   comment recording exactly why the force is required.
7. **The full documentation web landed** (audit doc
   `docs/research/2026-11-08_mkforce-audit.md` with per-site verdict
   tables + could-do-better + probe recipe; README index row; two
   TODO_LIST rows; vm-testing.md lesson CORRECTED in two passages — the
   old "mkForce neutralizes fileSystems" claim was wrong; AGENTS.md
   memory bullet; CHANGELOG `### Changed` entry same-window;
   initrd-audit's "mkForce'd stand-in root" comment de-staled).
8. **The complete cheap-gate battery green on the final tree:** treefmt,
   telephony-eval, prod-boot instantiation, doc-counts (49 checks /
   344 tests derived = claimed), markers-check, docs-drift,
   changelog-headings, rendering-audit, scrub-check (23 patterns),
   initrd-audit. The drift gate caught TWO of my own bad citations
   (`./sip.py`, `misc/freeswitch.nix` parsed as repo paths) — fixed by
   rewording; the gate did precisely its job.
9. **Live count re-verified against HEAD after the daemon sweep: 14
   `mkForce` call sites = the audit's claim.**

## b) PARTIALLY DONE

1. **Boot-level proof of telephony-prod-boot → open.** Eval-level proof
   is complete (probe A/B byte-identical; instantiation clean), but the
   suite derivation moved (suite-file edit → flake-source hash inside
   `tests/sip.py`), so the first post-audit `nix flake check` on CI is
   the boot-level proof. TODO row exists (Medium, "rides CI", evidence:
   audit doc + drv id).
2. **Commit attribution → open.** The work landed via 9 daemon
   heuristic commits (`080e5cb`, `001cc78`, `5f8aa0e`, `ab5532c`,
   `046623d`, `bcee705`, plus 3 post-session sibling commits) with
   arbitrary file grouping; content is verified landed (clean tree,
   14-site re-count, gates green on the final tree), but the
   lane-sequencing rule (hand-authored commit FIRST) was violated — see
   §d4. Whether to re-author is an owner call (§g2).
3. **The secrets.nix symmetry residue → open.**
   `turn.authSecret = mkForce ""` has no competing definition (option
   default is already `""`) and is decorative by the audit's own
   standard — kept only for lane symmetry with the two genuine
   lane-clears beside it, and the audit says so explicitly. Normalizing
   it is a 5-minute probe-provable edit left for the next train.
4. **CI-verdict observation → not yet possible.** No CI run over the
   audit-carrying head has been observed (nothing pushed by this
   session; the daemon pushes on its own schedule). The airtight
   `gh run view` protocol applies once a run exists.

## c) NOT STARTED

1. **Upstream nixpkgs freeswitch lane** (CPUSchedulingPolicy as
   mkDefault/option + a config-dir knob to retire our ExecStart
   mirror): owner-gated TODO row exists with the verify-before-filing
   gate named; zero work done.
2. **Inert-pattern sweep over the OTHER suites** — one grep
   (`fileSystems`/`grub` overrides in `tests/` beyond the six audited
   files) never ran; if another suite carries a framework-priority-10
   override it is silently inert the same way.
3. **The precedence probe as a checked-in repo tool** (scripts/ +
   self-test, the markers_check pattern): currently the recipe lives as
   prose in the audit doc and a /tmp file.
4. **Annotation of the 15:45 report's resolved items** (its §b1
   secrets.nix fix and §f1/f2 fax-feed items landed earlier today) with
   routed resolution markers — prior train's tail, untouched here.
5. **A grep-gate for the decorative-force smell** (new `mkForce` without
   an adjacent why-comment) — considered, judged likely
   over-engineering, not built; recorded as WORTH CONSIDERING in §f.

## d) TOTALLY FUCKED UP

1. **A semantic break almost shipped.** The grub.devices
   normalization changed the EFFECTIVE config (two boot devices), not
   just precedence decoration — my "plain suffices" theory was wrong
   about list-concat mirrors. It was caught only because the A/B probe
   was re-run after that specific edit (the plan had called for a
   single post-edit probe run). Had the plan been followed literally, a
   broken boot config would have reached CI. The save was the process,
   not foresight.
2. **The documented anti-pattern, executed twice in one command.**
   Ran the bash scrub script under `python3` (SyntaxError) and piped
   the failure through `| tail`, masking the real exit — the exact
   `PIPESTATUS`/redirect-then-`$?` discipline this repo codifies. Real
   exit captured on the retry (script is healthy; 23 patterns clean).
3. **Probe construction flailing: ~6 failed eval attempts** (pkgs.path
   missing on this flake's legacyPackages, pkgs.system missing,
   evalTest result shape surprise, my own sed/python mangles of the
   probe file, conflating the file's output attrset with the eval
   result) before the first clean verdict. Minutes wasted; the recipe
   is now written down so it is one-shot next time.
4. **Lane-sequencing violation.** Nix edits, doc lanes, and gate runs
   all sat uncommitted while I worked; the daemon bundled them into 9
   heuristic commits with arbitrary grouping (e.g. the audit doc
   landed with the TODO rows, the AGENTS memory with the CHANGELOG).
   The rule is hand-authored commit FIRST, then the next lane's edits.
5. **Concurrent sibling session detected late.** At 17:03–17:11 a
   sibling lane committed dialplan/default.nix/ops-runbook work. Zero
   file overlap and every probe verdict predates 17:03, but my final
   gate battery ran while their edits were landing — attribution is
   by-time only. The session-start lane probe covered processes, not
   mid-session re-checks.

## e) WHAT WE SHOULD IMPROVE

1. **A/B-probe after EVERY precedence edit**, not after the edit set.
   The grub catch proves the gate works only when actually run; the
   probe is eval-cheap, so there is no budget argument.
2. **Promote the probe to a repo tool** with a self-test so precedence
   questions are one command, not an archaeology session.
3. **One pass for normalize-or-comment.** Every force should leave the
   audit either required-with-a-comment or plain; the secrets.nix
   "kept for symmetry" residue is this audit's own inconsistency.
4. **Commit hand-authored per lane, gate-green gate-first.** The daemon
   heuristic bundling is only tolerable because the tree content is
   verified; the attribution cost was real (§b2).
5. **Re-check lanes mid-session**, not just at start: a sibling lane
   appeared 60 minutes in; a second `git status` before the final gate
   battery would have caught it before my gates ran on their tree.
6. **Cite stable names, not line numbers, in durable docs** — the audit
   doc cites qemu-vm.nix:1415 / freeswitch.nix:97; rev-pinned, but the
   pins are exactly what the next lock sweep moves. The standing rule
   is already in AGENTS.md; the audit doc half-follows it.
7. **Audit verdicts are pin-scoped**: the "upstream sets this plain"
   verdicts hold at `f9a75f41`/`e762f5af`; every future lock move
   re-opens them. That refresh trigger is in the README row — keep it
   visible in future relock runbook steps.

## f) Up to 50 things next (impact-sorted; 1–9 are this train's tails)

1. First post-audit CI run green (boot-level proof for prod-boot; rides
   CI, 0 effort) → open
2. Airtight CI verdict over that head (`gh run view --repo` with step
   timestamps; cancel ≠ red protocol) → open
3. Normalize secrets.nix `turn.authSecret = mkForce ""` → plain
   (probe + drv-equality proof; close the audit's one residue) → open
4. Inert-pattern sweep: `grep fileSystems/grub tests/` beyond the six
   audited files; every framework-priority-10 override found is
   silently dead → open
5. Annotate the 15:45 report's resolved items (§b1, §f1/f2) with routed
   markers; archive it when fully resolved → open
6. Precedence probe as `scripts/` tool + self-test (evalTest route,
   gotchas encoded) → open
7. Re-author the audit's daemon commits hand-authored (soft-reset +
   re-author, unpushed-only, race-aware) — owner call first (§g2) → open
8. Stash@{0} disposition: prove subset-of-landed (WIP on 41ec5c5 vs
   superseding commits' stats), then drop — owner call (§g3) → open
9. Replace the audit doc's line-number cites with rev-pinned stable
   names → open
10. Owner-gated: draft the nixpkgs freeswitch upstream issue/PR
    (verify-before-filing first; motivation = mirror-drift risk) → open
11. Consider a cheap grep gate: `mkForce` without an adjacent
    why-comment fails treefmt-statix-style → WORTH CONSIDERING
12. Add the "decorative force = plain assignment" rule to the session
    nix-review checklist (skill lives in crush-config; by commit) → open
13. Standing rule into the relock runbook: after ANY webphone/nixpkgs
    lock move, re-run the audit's upstream verification (the plain-def
    verdicts are pin-scoped) → open
14. Watch doc-counts while the sibling dialplan lane lands (its
    default.nix edit may add checks; the 49-claim must track) → open
15. Verify the sibling lane's dialplan work did not shift my gate
    verdicts: re-run doc-counts + markers-check on their landed head → open
16. Feed the vm-testing lesson correction back into the
    metal-boot/prod-boot header comments for consistency (metal-boot's
    header still says "boots a mkForce'd stand-in root" — accurate for
    the DRIVES force but worth one clarifying word) → open
17. When the next webphone sweep lands: re-verify web.nix's caddy/csrf
    comment claims against the new module source (2-minute grep, the
    audit's §upstream facts) → open
18. ROADMAP: record the nixpkgs-upstream option wish (conf-dir knob) as
    a raw idea so the TODO row has a long-term home → open
19. Extend the audit doc with a "how to add a new force" checklist
    section (name the competitor first) → open
20. Consider `virtualisation.fileSystems` (the framework-documented API)
    as the pattern for any FUTURE prod-boot filesystem need — document
    in vm-testing if ever needed → WORTH CONSIDERING
21. Probe coverage: run the same evalTest probe for telephony-metal-boot
    to print its effective drives list (verifies the concat-replace
    claim end to end; the source read says required, the probe would
    prove it) → open
22. Add the CHANGELOG's drv-id citation style to the conventions
    discussion (drvPaths are content-verifiable; line cites rot) →
    WORTH CONSIDERING
23. Session-start ritual addition: `git log -n 3 --format=%ci` to catch
    sibling lanes by TIME, not just by process list → open
24. When archiving this report: run check-rows uniformity pass per
    convention → open (naturally, at archive time)
25. markers_check monotonicity: this report adds no archived-surface
    content; nothing to do — recorded so the next sweep does not
    re-derive → informational
26. Sweep-source instrumentation remains open fleet-wide (unattributed
    `nix flake update` runs); the audit adds no new evidence — keep the
    existing TODO row hot → open (pre-existing row)
27. Upstream webphone idea (owner-gated): surface "which module defs are
    plain vs mkDefault" in upstream's module docs, so consumer guards
    like web.nix's force can be weaker → WORTH CONSIDERING
28. Evaluate whether pbx.nix's ExecStart mirror can derive from
    upstream's value at eval time (string surgery on
    `config.services.freeswitch`'s ExecStart) instead of a literal
    mirror — fragility tradeoff, needs a probe → WORTH CONSIDERING
29. Keep the audit doc's "standing rule" paragraph in sync with AGENTS
    (one home per fact; AGENTS carries the rule, the audit carries the
    narrative — verify no drift next docs pass) → open
30. Everything else observed this session was gate-clean; no further
    tails. (Honest cap below 50 — padding a next-list is how stale
    rows are born.)

## g) Questions for the owner (owner-only, ≤3)

1. **Upstream filing:** proceed with the nixpkgs freeswitch issue/PR
   (CPUSchedulingPolicy as mkDefault or an option; a config-dir knob to
   retire our ExecStart mirror) after verify-before-filing — or keep it
   documented-only?
2. **History:** the audit rides 9 daemon heuristic commits (unpushed).
   Re-author into one hand-authored commit (`git reset --soft`, race
   per the 2026-10-05 lesson) — or let heuristic history stand?
3. **Stash@{0}** (`WIP on main: 41ec5c5`, daemon-era "3 changed
   file(s)", predates this session): run the subset-of-landed proof and
   drop it, or keep it for your own review?
