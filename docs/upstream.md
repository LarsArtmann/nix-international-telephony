# Upstream contributions

Tracked work to give back to the ecosystem, with the evidence we already
hold. Everything here follows the verify-before-filing rule: each item
names the source-level verification behind it.

## nix-ssh-config: keys-only leaves kbd-interactive on

**Filed:** [LarsArtmann/nix-ssh-config#1](https://github.com/LarsArtmann/nix-ssh-config/issues/1)
**RESOLVED upstream in [v0.1.2](https://github.com/LarsArtmann/nix-ssh-config/releases/tag/v0.1.2) (2026-08-29).** The module now defaults
`KbdInteractiveAuthentication` to follow `passwordAuthentication`, so
keys-only means keys-only; our flake input is pinned to `v0.1.2` and the
downstream workaround is retired. `tests/ssh.nix` keeps its
`kbdinteractiveauthentication no` assertion — it now guards the upstream
default instead of our workaround. (Historical detail: the workaround was
`extraSettings.KbdInteractiveAuthentication = false` + a VM-test
assertion in `tests/ssh.nix`.)

## nixpkgs: freeswitch unit should order after network-online.target

**Status:** PR prep (not yet filed)

Symptom we hit twice: sofia resolves `$${local_ip_v4}` by
UDP-connecting outward; when no default route exists yet at unit start
it silently binds `127.0.0.1` and the PBX stays unreachable until a
manual restart. On slow-network boots this masquerades as a "profile
start wedge" (full story: our AGENTS.md, "sofia binds" note).

Prep checklist for the nixpkgs PR:

- [ ] Reproduce on stock `services.freeswitch` (no our-module config):
      delay the default route, observe `ss -ltn` binding 127.0.0.1.
- [ ] Change: `after = [ "network-online.target" ]` +
      `wants = [ "network-online.target" ]` in the nixpkgs module's
      unit (nixos/modules/services/misc/freeswitch.nix).
- [ ] Test: a nixosTests variant with a scripted late route.
- [ ] Filing target: NixOS/nixpkgs, `nixos/modules/services/misc`.

## services.telephony upstreamability checklist

What a nixpkgs/FAQ review would ask before this module could move
upstream, in rough order:

1. **Module review shape**: options all typed + described (done),
   `mkIf cfg.enable` wrappers (done), assertions (done — and their
   rejection paths now tested).
2. **nixpkgs module conventions**: no `warnings`, no `mdDoc`, examples
   `literalExpression` where store-pathed (mostly done), option docs
   rendered via `man services.telephony` — needs an options doc pass.
3. **Test suite in nixosTests shape**: our suites are standard
   `testers.nixosTest` modules; the browser suite stays out (chromium
   closure) — upstream would take the SIP-level ones.
4. **The generated-config design**: nixpkgs reviewers historically
   prefer upstreamable generators over XML templating in Nix; the
   strongest pitch is exactly our regression-tested eval checks.
5. **Inputs to drop first**: the flake's only runtime module input is
   nix-ssh-config (host-level, not part of `services.telephony`) —
   the telephony module itself is dependency-free.

Not planned until a real deployment proves the module shape in
production (ROADMAP Q4).
