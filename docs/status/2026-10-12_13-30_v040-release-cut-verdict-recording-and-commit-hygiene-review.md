# Full status — 2026-10-12 13:30 CEST — v0.4.0 release cut, verdict recording, and commit-hygiene review

Session continuation after the round-11 handoff. Scope: the handoff's open items
(marker debt, CI verdict, release cut) executed end to end, plus an honest
account of what went wrong along the way. Two agent lanes remain active in this
tree (the sibling session landed daemon shards `df4c56d` (13 files) and
`d4e7bb7` (3 files) minutes before this report — their freeswitch-modules
split is in flight).

## a) FULLY DONE

1. **Marker debt cleared** (commit `d7d49f9`): the two §g findings on the
   08-45 report got `→ open — owner` verdicts; item 1 also received a REAL
   verdict (it had only passed the scanner via the accidental `M02 → M04`
   arrow inside its prose — a false-negative pass worth closing).
2. **Origin CI watched to green over the round-11 tree**: run `38213939150`
   over `3b63222` completed SUCCESS (both main jobs: the x86
   `nix flake check` and the aarch64 TCG boot test; airtight
   headSha read). The sibling's `telephony-webphone-dynamic-directory`
   suite was fixed by their lane before that run.
3. **M03 final verdict recorded** (commit `bb6cfc2`): TODO_LIST's CI-posture
   row narrowed to branch-protection-only with the green runs as evidence;
   the 08-45 report's verdict-watch items annotated `→ done`.
4. **v0.4.0 released** — the handoff said "cut v0.3.0"; that tag already
   existed since 2026-09-30, so the cut shipped as **v0.4.0** instead:
   CHANGELOG `## [0.4.0] - 2026-10-12` dated with a fresh empty
   `[Unreleased]` above it, stale TODO row deleted (release commit
   `8711531`), pushed, **CI-proven BEFORE tagging** (run `38231608546`,
   green on both main jobs, airtight headSha match), then annotated tag +
   `gh release create v0.4.0` with digest notes covering the voice agent,
   passkeys, dynamic SIP directory, pbx-lens analytics, platform fixes,
   and the gate machinery.
5. **Repo metadata refreshed** (M16.3): description now names the current
   feature surface (passkey webphone, Telnyx SMS/WhatsApp bridge) and
   `telnyx` + `voip` topics added.
6. **Release/verdict items annotated done in both round-11 reports**
   (commit `c043434`), full local gate battery green after: markers 78/0,
   rendering 78/0, drift PASS, changelog-headings PASS, `nix fmt` clean.
7. **Four live incidents handled without data loss**: a daemon commit race
   on the TODO deletion (soft-reset + immediate re-author), a CHANGELOG
   mtime touch by `nix fmt` mid-edit (re-read, re-applied), a stale
   `index.lock` (7.5 min old, verified no owning process, trashed), and a
   pre-staged sibling file discovered inside my commit (assessed — see d2).

## b) PARTIALLY DONE

1. Commit `c043434`'s contents vs its message → open — the annotations
   commit accidentally includes the sibling's pre-staged
   `modules/telephony/freeswitch-modules.nix` (85 lines) that their
   crashed git operation left staged; the message describes docs-only
   changes and never mentions the third file. The snapshot parses clean
   and CI over the adjacent daemon commit was green, but the durable
   attribution lives only in session chat, not in any repo doc.
2. CI verdict for `c043434` itself (run `38242096364`) → open — in flight
   at write time; the committed tree contains the sibling's coherent
   snapshot, but I did not wait for or record the verdict.
3. Working-tree eval state → open — `telephony-eval` failed twice on the
   sibling's LIVE working tree with two different transient errors
   (a `libopus,` syntax error, then a stack overflow); both were their
   mid-edit state, and the committed snapshots parse — but no settled,
   full-gate verification of the final tree exists yet.
4. Sibling-lane monitoring → open — passive only: their suite green in the
   verdict run, their new module split observed landing; no deep review
   (deliberately — their files, their lane).

## c) NOT STARTED (owner rows; carried, not re-researched)

1. M01/M02 first-call close-out via `scripts/verify-live.sh` → open — owner
   hands-on (portal + live host).
2. M06 branch protection from the `docs/ci-posture.md` packet → open —
   owner admin call (blocks daemon pushes while red; the packet's context
   names predate the notify-failure job and need a refresh pass).
3. `ALERT_WEBHOOK` repo secret → open — owner (the notify lane is
   otherwise wired and proven to matter).
4. M11 Telnyx API-key rotation + scrub-pattern prefix update in the same
   action → open — owner.
5. Warsaw DID re-purchase + 5 KYC items, then DE national DID → open —
   owner (portal, deadline-bound once started).
6. F37: global `~/.gitconfig` `core.hooksPath` landmine → open — owner
   (home-manager level).
7. M18/M19 live-host work: CDR cancelled-leg reproduction, WhatsApp live
   round trip → open — owner (needs the live host / a real WABA).
8. fspbx trial verdict sign-off → open — owner (kill/keep decision).

## d) TOTALLY FUCKED UP

1. **The release version check was luck, not process**: I proceeded toward
   the handoff's "cut v0.3.0" and only discovered the collision because a
   heading-convention check happened to surface `## [0.3.0] - 2026-09-30`
   in the CHANGELOG. Verifying the latest tag should have been step ZERO
   of the release cut, before any edit. Had I followed the handoff
   blindly, I would have tried to tag an existing release name.
2. **The c043434 sweep**: after trashing the stale lock I re-ran
   `git add <two files>` and committed WITHOUT re-inspecting the staged
   state — the sibling's orphaned staged file rode along. The pre-commit
   output even printed the unstaged-files stash warnings and I read past
   them. The correct tool was `git commit <pathspec>` (commits exactly the
   named paths) or a `git diff --cached --stat` check first. Not a data
   loss, but a mis-attributed commit is on pushed main forever.
3. **The release-notes round trip**: `/tmp` is not persistent across bash
   calls in this environment; `gh release create --notes-file` failed once
   on the vanished file. Should have piped via heredoc/`--notes -` in the
   same invocation, or written the file and created the release in one
   command chain.

## e) WHAT WE SHOULD IMPROVE

1. **Post-lock-incident commit ritual**: after ANY `index.lock` incident,
   run `git status` + `git diff --cached --stat` before the next commit;
   prefer `git commit <pathspec>` when only specific files are intended.
   Worth an AGENTS.md line — this repo's two-agent-plus-daemon setup makes
   orphaned staging a recurring hazard.
2. **Release step 0 = version verification**: `git tag` + `gh release
   list` BEFORE touching the CHANGELOG; the handoff-summarized next
   version is a claim, not a fact.
3. **Release notes in one invocation**: heredoc into `gh release create
   --notes -`, never an unverified `/tmp` handoff between calls.
4. **Probe the COMMITTED tree, not the churn**: for verdicts on mixed-lane
   trees, eval a detached `git worktree` at the commit under test instead
   of the moving working tree (my two eval probes measured the sibling's
   keystrokes, not any tree state).
5. **Durable incident records**: near-misses and accidental inclusions get
   written into a status report §d (this one) — chat text is not memory.
6. **A release-cut checklist in `docs/ops-runbook.md`** (version check →
   date CHANGELOG → commit → CI green → annotated tag with run ID →
   release with digest notes → metadata refresh → annotate reports) would
   have prevented every d-item above; the lock-bump runbook proves the
   pattern works here.
7. **Watch runs via one background `gh run watch`** and read its final
   verdict, instead of the several manual polls I did.

## f) UP TO 50 THINGS WE SHOULD GET DONE NEXT

1. Watch run `38242096364` (over `c043434`) to a completed verdict and
   record it → open — agent, ~1h.
2. Record the c043434 attribution correction durably: one append-only
   CHANGELOG line noting `freeswitch-modules.nix` entered via the
   annotations commit → open — agent, 5min.
3. Add the release-cut checklist to `docs/ops-runbook.md` (§e 6) → open —
   agent, 20min.
4. Add the post-lock commit ritual to AGENTS.md (§e 1) → open — agent,
   5min.
5. Once the sibling's module split settles: full local gate battery
   (markers, rendering, drift, fmt, unittest, `nix flake check
   --no-build`) on the tree at rest → open — agent, gated on their lane.
6. Harvest the still-open handoff items into TODO_LIST rows (lock_guard
   pbx-lens extension, per-item self-classification, dynamic-directory
   feature row) → open — agent, 15min.
7. Re-run `scripts/doc_counts.py` after the sibling's check-set changes
   land (44/169 will drift again) and fix FEATURES/AGENTS claims → open —
   agent, 10min.
8. Verify the rendered v0.4.0 release page on GitHub (notes formatting) →
   open — agent, 2min.
9. Compare the v0.4.0 release shape vs v0.3.0 (assets policy, body style)
   for consistency → open — agent, 5min.
10. Refresh the `docs/ci-posture.md` protection packet with the current
    context names (notify-failure exists now) → open — agent, 10min.
11. Branch protection decision + application → open — owner (admin).
12. `ALERT_WEBHOOK` secret + one live fire-drill of the notify job →
    open — owner then agent drill.
13. Watch main's CI back to green AFTER the sibling's split lands (the
    next green completed run is the new "tree at rest" anchor) → open —
    agent.
14. Archive the 07-15 and 08-45 reports plus this one once every item
    carries markers (annotate → `git mv` to `docs/status/archived/` +
    check-rows uniformity pass) → open — agent, next docs pass.
15. October snapshot ANNOTATE+ARCHIVE batch (the 2026-10-01→07 clusters;
    18 status + 3 planning snapshots per the 07-15 inventory) → open —
    agent, round-12 scoping.
16. lock_guard pbx-lens extension (the commit-msg guard covers only the
    webphone rev today) → open — agent, 30min.
17. Per-item self-classification arm for markers_check → open — agent.
18. M01/M02 first-call close-out → open — owner.
19. M18 CDR cancelled-leg reproduction on the live host → open — owner
    (gated on live host).
20. M19 WhatsApp live verification (portal embedded signup, VOICE OTP,
    both-direction round trip incl. media) → open — owner.
21. M11 Telnyx API-key rotation + scrub-pattern prefix update → open —
    owner.
22. Warsaw DID KYC re-purchase inside the 48h window; DE national DID →
    open — owner.
23. M06 branch protection application → open — owner.
24. F37 home-manager hooksPath landmine → open — owner.
25. fspbx trial verdict sign-off (revoke PAT + trash VM, or keep) → open —
    owner.
26. sops-nix example-host wiring (docs recipe stands) → open — owner.
27. Browser E2E CI promotion from manual dispatch → open — owner call on
    gating.
28. `flake-meta-checker` mainProgram policy: accept remainder vs upstream
    carve-out → open — owner.
29. GitHub residual-exposure appetite after the history rewrite (support
    GC + clone inventory) → open — owner.
30. pbx-lens lint debt dispatch — coordinate with the active pbx-lens
    session, do not fix under it → open — agent coordination, then Lint
    lane to green.
31. Confirm the GitHub flake-update bot's "allow Actions to create/approve
    PRs" toggle (the Sep/Oct runs died on it) → open — owner settings.
32. Delete the stale `chore/flake-update-2026-09` branch on origin after
    owner confirm → open — owner.
33. Decide whether future releases keep the CI-proven-before-tag gate and
    drop the "first real call" gate (this release set the precedent) →
    open — owner.
34. Consider tag protection once branch protection lands (release tags
    should be immutable) → open — owner.
35. After the sibling settles: re-diff the pbx.nix FreeSWITCH module list
    against nixpkgs' default set (AGENTS.md standing instruction) → open —
    agent.
36. Verify `git describe` on main now resolves to `v0.4.0-<n>-g<sha>` as
    expected (tag predates several daemon shards) → open — agent, 1min.
37. Re-check `gh api repos/<owner>/<name>/commits/HEAD` freshness for the
    webphone + pbx-lens inputs at the NEXT relock window → open — agent
    (standing ritual).
38. Add `coturn`/`turn` topics (description mentions coturn; topics don't)
    → open — agent, 1min.
39. Annotate the 08-45 §b.4 pbx-lens lane item when the sibling session
    reports its Lint lane green → open — agent.
40. Confirm no release assets policy divergence (source-only releases are
    the repo convention) → open — agent, 2min.

## g) QUESTIONS I CANNOT FIGURE OUT MYSELF

1. Branch protection on main: the tree is calm post-release RIGHT NOW —
   apply Option A from the ci-posture packet immediately (both agent
   lanes wedge on every red push), or keep main unprotected while the
   sibling's split is still landing? → open — owner.
2. The `c043434` mis-attribution: leave pushed history untouched (my
   recommendation — the CHANGELOG correction line in §f 2 is the durable
   record), or do you want a visible note (commit comment / release-note
   mention) for anyone auditing that commit? → open — owner.
3. Release gating going forward: v0.4.0 anchored a CI-proven tree before
   the owner's live-host churn — should the "first real call" gate stay
   retired for future minor releases, or does it still stand as the
   owner's timing control? → open — owner.
