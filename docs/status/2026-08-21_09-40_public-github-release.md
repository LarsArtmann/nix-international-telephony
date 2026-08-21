# Status: Public GitHub release v0.1.0 shipped

**Date:** 2026-08-21 09:40 CEST
**Session:** user asked for a public GitHub release; audit → artifacts →
verify → publish → CI green.
**Repo:** https://github.com/LarsArtmann/nix-international-telephony
**Release:** https://github.com/LarsArtmann/nix-international-telephony/releases/tag/v0.1.0

---

## What was done

1. **Pre-public security audit** — grepped the whole tree and the 2-commit
   history for tokens/private keys/credentials/real IPs: clean. Only
   `demo-*` placeholders, fictional `441632960961` numbers and
   `*.example.com` domains (demo VM config, loudly flagged in README).
2. **Release artifacts** (exactly the gaps the v0.1 retrospective listed):
   - `LICENSE` — MIT, `Copyright (c) 2026 Lars Artmann` (matches ActaFlow /
     ArtCode pattern; README already claimed MIT).
   - `CHANGELOG.md` — Keep a Changelog format, `[0.1.0] - 2026-08-21` with
     an honest "Known limitations" section.
   - `.github/workflows/ci.yml` — GitHub Actions running the full
     `nix flake check` gate on `ubuntu-latest`; udev rule
     (`99-kvm4all.rules`) opens `/dev/kvm` so the NixOS VM test runs with
     acceleration on hosted runners.
   - **SIP.js MIT notice** shipped as `sip.min.js.LEGAL.txt` next to the
     bundle: esbuild's `--legal-comments=external` turned out to emit
     nothing (sip.js `lib/*.js` carry no license comment — first build
     failed on the missing file), so the npm tarball's `package/LICENSE.md`
     is copied instead. Also fixed the pre-existing
     `cp: source file specified more than once` warning in installPhase.
   - README fixes: real flake input URL (was broken `YOUR Fork`
     placeholder), stale `nix fmt` line, CI badge, license section pointing
     at LICENSE + the LEGAL.txt.
3. **Verification** — `nix build .#webphone` (fast esbuild feedback),
   `nix fmt -- --fail-on-change`, full `nix flake check`: all green locally.
4. **Publish** — branch renamed `master` → `main`; repo created public;
   annotated tag `v0.1.0` pushed; GitHub Release published with
   highlights + known-limitations notes.
5. **CI verified end to end twice** — first run green in 1m38s (VM test
   included, KVM fix works). Its only annotations: Node-20 deprecation
   (actions) and a GitHub cache-service hiccup ("Failed to save", not
   ours). Bumped `actions/checkout@v4→v7` and
   `nix-installer-action@v16→v22` (current majors per GitHub API) and
   pushed; second run verified.
6. **AGENTS.md updated** — public repo URL, note that the local directory
   keeps the historical `internatial` typo (GitHub name is the correct
   spelling), CI/release conventions, LEGAL.txt lore.

## Decisions

- **Repo name spelled correctly on GitHub** (`nix-international-telephony`);
  the local directory was NOT renamed (would break the active shell cwd).
  Optional follow-up: `mv` + `git remote` stays valid.
- MIT chosen over PROPRIETARY because the README and the retrospective
  already committed to MIT and the project fetches MIT/CC-BY assets.
- No FEATURES.md/TODO_LIST.md/DOMAIN_LANGUAGE.md in this release — still
  open from the v0.1 retrospective next-steps list, not release-blocking.
  _(Update 2026-08-21, later the same morning: all three now exist — added by a
  docs-health pass together with ROADMAP.md.)_

## Open / next

- Everything in the v0.1 retrospective's NEXT list still applies (secrets
  via sops-nix, browser E2E test, acme TLS mode, ...).
- GitHub cache-save annotation is a GitHub-side service blip; revisit only
  if it recurs.
