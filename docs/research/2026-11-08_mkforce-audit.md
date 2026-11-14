# mkForce audit — every `lib.mkForce` in the tree (2026-11-08)

Point-in-time review of all live `mkForce` usages: why each exists, whether it
is load-bearing, and how the tree could carry fewer of them. Method: read every
usage in context, trace what it competes against in the pinned upstream sources
(nixpkgs `f9a75f41`, webphone `e762f5af`), then PROVE verdicts with an
eval-only machine-config probe (recipe at the bottom) — no VM runs spent.

## The precedence model this audit corrected

At each option NODE, the module system keeps only the definitions in the
lowest-priority group and **discards every higher-priority definition
entirely**. Priorities in play here:

| Constructor                   | Priority | Loses to                  |
| ----------------------------- | -------- | ------------------------- |
| plain assignment              | 100      | `mkForce`, `mkVMOverride` |
| `mkDefault`                   | 1000     | plain, `mkForce`          |
| option `default`              | 1500     | everything above          |
| `mkForce`                     | 50       | `mkVMOverride` only       |
| `mkVMOverride` (VM framework) | 10       | nothing in this tree      |

Two consequences the tree's forces live or die by:

1. **List options concat instead of conflicting**: two plain definitions of a
   `listOf` option merge by concatenation, so REPLACING a framework-built list
   (qemu drives, grub devices) needs `mkForce` — but any other plain/derived
   definition at the same priority concatenates in too (caught live below).
2. **`mkForce {}` on an attrsOf subtree erases sibling leaves** defined
   elsewhere at lower precedence (probe: `networking.interfaces.ens3` comes
   out empty against the template's plain addresses), while the same `mkForce`
   against the framework's `fileSystems` **loses silently** because the
   framework overrides at priority 10.

## Inventory (14 remaining sites — every one verified load-bearing)

### modules/telephony/pbx.nix (2) — overriding upstream nixpkgs plain values

| Site                                                      | Overrides                                                                                   | Verdict                                                                                                                                                      |
| --------------------------------------------------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `serviceConfig.CPUSchedulingPolicy = mkForce "other"`     | nixpkgs `freeswitch.nix` sets `CPUSchedulingPolicy = "fifo"` PLAIN (misc/freeswitch.nix:97) | **Required.** A plain re-definition would conflict. The why is in the comment: no RT budget upstream, CFS is right for this stack.                           |
| `ExecStart = mkForce (...-conf /var/lib/freeswitch/conf)` | upstream ExecStart is PLAIN with `-conf ${configPath}`                                      | **Required.** Secret-file mode redirects the config dir; mirroring upstream's line is the only mechanism until nixpkgs exposes a knob (upstream lane below). |

### modules/telephony/web.nix (1) — split-brain guard

| Site                                             | Overrides                                                                                     | Verdict                                                                                                                                                                                                                                                                                      |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `services.webphone.caddy.enable = mkForce false` | nothing today (upstream option default; the Caddy generator is gated `mkIf cfg.caddy.enable`) | **Guard, deliberately stronger than needed.** Plain `false` would suffice today; the force survives upstream default flips (the v2.8.0 generator churn is real precedent) AND blocks operator plain-enables, which the paired `default.nix` assertion turns into a legible eval error. Kept. |

### tests/secrets.nix (4) — fixture lane swaps + exactly-one-of arithmetic

| Site                                                | Overrides                                                        | Verdict                                                                                                                            |
| --------------------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `eventSocketPassword = mkForce ""`                  | `tests/common.nix` baseTelephony sets the plain fixture password | **Required.** `exactlyOneSecret` counts `""` as unset; without the clear, both lanes are set and the assertion fires.              |
| `extensions."1000".password = mkForce ""`           | same, per-extension                                              | **Required**, same arithmetic. (1001 deliberately keeps its plain password — the mixed-mode proof.)                                |
| `turn.authSecret = mkForce ""`                      | — no competitor (fixture sets only the file form)                | Overkill-as-written, kept for symmetry with the two lane-clears beside it; `""` is already the option default.                     |
| `turn.authSecretFile = mkForce "/run/secrets/turn"` | fixture's `/etc/telephony/turn-secret`                           | **Required** — this suite provisions its OWN secret-manager-shaped file, the path is load-bearing (the suite's oneshot writes it). |

### tests/eval.nix (2, after this audit) — eval-arm lane proofs

| Site                                                          | Overrides                                   | Verdict                                                                                                                                                                                                                                     |
| ------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `authSecretFile = mkForce null` (crmEval)                     | fixture tls-mode-host.nix's plain file form | **Required.** Only a clear of a fixture value needs priority; the inline secret itself is now a plain assignment (normalized in this audit — `authSecret` had no competitor).                                                               |
| `authSecretFile = mkForce "/run/secrets/turn"` (turnFileEval) | fixture's plain file path                   | **Required for the arm's self-documenting path.** For an eval-only arm the fixture's path would serve the assertions equally; the `/run/secrets` shape is the deliberate, CHANGELOG-documented lane statement (2026-11-08 eval-heal). Kept. |

### tests/metal-boot.nix (1) — list replace

| Site                                                 | Overrides                                                                                                                       | Verdict                                                                                                                                                                                 |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `virtualisation.qemu.drives = mkForce [ root-only ]` | framework builds the drive list via `mkMerge` of plain defs (root + store image + every `emptyDiskImages` entry) — lists concat | **Required.** The whole point is to strip empty0.qcow2 off the virtio-blk bus (it is re-attached on the virtio-scsi HBA via `qemu.options`); concatenation could never remove an entry. |

### tests/prod-boot.nix (4) — VM adaptations of a deliberately plain template

| Site                                                             | Overrides                                                                                                                            | Verdict                                                                                                                                                                                                                                                                                                                                   |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `services.telephony.tls = mkForce { mode = "self-signed"; ... }` | hosts/pbx-prod's plain `tls.mode = "acme"`                                                                                           | **Required.** ACME cannot issue in a VM; acme wiring is eval-covered by telephony-eval.                                                                                                                                                                                                                                                   |
| `networking.interfaces.ens3 = mkForce { }`                       | template's plain Hetzner IPv6 config                                                                                                 | **Required.** Probe: effective `ens3.ipv6.addresses = []` — the force erases the subtree (lowest-priority group wins). The 2026-09-03 wedge (network-addresses-ens3 parked on a device that never appears) is exactly what this prevents; the `systemd.services.network-addresses-ens3.enable = false` line beside it is belt-and-braces. |
| `networking.defaultGateway6 = mkForce null`                      | template's plain gateway                                                                                                             | **Required.** Probe: effective `null`.                                                                                                                                                                                                                                                                                                    |
| `boot.loader.grub.devices = mkForce [ "/dev/vda" ]`              | grub's device→devices mirroring adds a plain-priority entry (`/dev/disk/by-id/virtio-root`) — with lists that CONCATS, not conflicts | **Required, probe-proven both directions.** This audit briefly normalized it to a plain assignment; the A/B probe showed the effective list becoming `["/dev/vda", "/dev/disk/by-id/virtio-root"]` (two boot devices) and it was reverted within minutes. The comment on the line now records the trap.                                   |

## What this audit changed (all zero-effective-config-delta, proof per change)

1. **tests/eval.nix — three decorative forces normalized to plain assignments**
   (crmEval's `authSecret`, turnFileEval's `authSecret`, the negative turn
   arm's `authSecret`). None had a competing definition; forcing them
   misread as "I am overriding something" and sent the next reader hunting
   for a competitor. Now consistent with the other three exactly-one-of
   negative arms, which were already plain. Proof: the telephony-eval check
   derivation is value-level (verdict strings + toplevel drvPaths only) —
   post-edit instantiation resolved to the byte-identical drv
   (`1j9psf51479vnc9vdpxd3clnmyzdpc0j`), `--rebuild` output-verification
   exit 0. Verdicts unchanged.
2. **tests/prod-boot.nix — the inert `fileSystems."/"` block removed.** The
   VM framework overrides `fileSystems` at `mkVMOverride` priority 10
   (qemu-vm.nix:1415), which beats `mkForce` (50): the suite's forced
   `/dev/vda` device never took effect — the machine always booted the
   framework's `/dev/disk/by-label/nixos` root. Probe A/B: effective root
   device/fsType byte-identical before/after removal. (This also corrects
   the vm-testing lesson's claim that mkForce "neutralizes" fileSystems.)
3. **tests/prod-boot.nix — the grub.devices force documented in place**
   (comment + the two-direction probe story above) after the failed
   normalization.

Counts: 19 live sites before → 14 after; the 14 remaining are all
required-or-guarded, each with its why in a code comment or this table.

## How we could do better

**Done in this audit**

- Normalize decorative forces (no competitor → plain) so every remaining
  force signals a real precedence fight. eval.nix done; secrets.nix's
  `turn.authSecret = mkForce ""` kept only for lane symmetry.
- Delete inert overrides instead of shipping config that silently loses
  (prod-boot fileSystems).

**Left as TODO rows (bounded, actionable)**

- **CI re-proof**: telephony-prod-boot's derivation moves (suite file edit →
  flake-source hash in `./sip.py`), so its first post-audit CI run is the
  boot-level proof. Eval-level proof is done (probe A/B identical;
  instantiation clean).
- **Upstream lane (nixpkgs freeswitch)**: `CPUSchedulingPolicy` as
  `mkDefault` and/or a config-dir option would retire the ExecStart mirror.
  Gate: verify-before-filing, then file with the mirror-drift risk as
  motivation. Owner call before filing.
  → Drafted 2026-11-14 (verified at the pin; the config-dir knob
  already EXISTS upstream, narrowing the ask to the two plain defs):
  `docs/drafts/2026-11-14_nixpkgs-freeswitch-mkdefaults.md` —
  file-ready, submission stays an owner call.
- **Considered and rejected**: parameterizing `tests/common.nix` with a
  secret-lane knob (plain/file) so suites would not need lane-clearing
  forces. Cost: fixture churn across every suite, for sites whose inline
  comments already carry the full story. The four `mkForce ""`/path swaps
  in secrets.nix are the honest shape of "this suite overrides the shared
  fixture".

**Standing rule for future work** (now in AGENTS.md): before writing a
`mkForce`, name the definition it fights; if you cannot, it is decorative —
write a plain assignment. And never trust "mkForce is stronger" against the
VM framework: `mkVMOverride` (priority 10) wins, and list options concat
where attrs conflict.

## Probe recipe (reusable, eval-only, no VM build)

Replicates a `runNixOSTest` suite's machine node and prints the EFFECTIVE
config values, so precedence questions get answers in seconds:

```nix
# /tmp/probe.nix — nix eval --impure --json --file /tmp/probe.nix
let
  f = builtins.getFlake "/home/lars/projects/nix-international-telephony";
  sys = "x86_64-linux";
  pkgs = import f.inputs.nixpkgs { inherit sys; };
  testLib = import (f.inputs.nixpkgs.outPath + "/nixos/lib/testing-python.nix") {
    inherit (pkgs) system;
    inherit pkgs;
  };
  suite = import "/home/lars/projects/nix-international-telephony/tests/<suite>.nix" {
    telephonyModule = f.nixosModules.telephony;
    webphonePackage = f.inputs.webphone.packages.${sys}.webphone;
    sshServerModule = f.inputs.nix-ssh-config.nixosModules.ssh;
  };
in (testLib.evalTest { imports = [ suite ]; }).config.nodes.machine
# NOTE: nodes.machine IS the config (no trailing .config), unlike
# NixOS system configs. Diff the JSON before/after any precedence edit.
```

Gotchas learned while building it: `pkgs.path` is absent from this flake's
`legacyPackages` (use `f.inputs.nixpkgs.outPath`); `builtins.getFlake` on a
path string needs `--impure` and exposes no `self` (import suite files by
absolute path instead); the `.test` passthru on `runNixOSTest` results is
the derivation itself, not the eval — the evalTest route above is the only
direct route to the machine config.
