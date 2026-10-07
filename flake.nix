{
  description = "NixOS telephony stack: FreeSWITCH PBX with WebRTC webphone, STUN/TURN, recording, ITSP gateway";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Hardened, post-quantum-ready SSH server for the example host
    # (services.ssh-server) and the tracked operator keys (sshKeys).
    # Tracks main; the exact revision lives in flake.lock only.
    nix-ssh-config = {
      url = "github:LarsArtmann/nix-ssh-config";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
    };

    # The webphone UI lives in its own repo (extracted 2026-09-17): a
    # single Go binary (v2) whose NixOS module (services.webphone) this
    # flake imports through nixosModules.telephony. Tracks main; the
    # exact revision lives in flake.lock only.
    webphone = {
      url = "github:LarsArtmann/webphone";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    treefmt-nix = {
      url = "github:numtide/treefmt-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    git-hooks-nix = {
      url = "github:cachix/git-hooks.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Declarative partitioning for the production host (hosts/pbx-prod/
    # disk.nix); nixos-anywhere executes it during install.
    disko = {
      url = "github:nix-community/disko";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    inputs@{
      self,
      flake-parts,
      nixpkgs,
      ...
    }:
    let
      telephonyModuleRaw = import ./modules/telephony;
      # Self-contained by default: consumers of nixosModules.telephony get
      # the webphone package from this flake's webphone input unless they
      # set services.telephony.webphone.package themselves, plus the
      # webphone repo's own services.webphone module (the service unit the
      # stack's nginx vhost reverse-proxies; see modules/telephony/web.nix).
      telephonyModule =
        { pkgs, lib, ... }:
        {
          imports = [
            telephonyModuleRaw
            inputs.webphone.nixosModules.default
          ];
          services.telephony.webphone.package =
            lib.mkDefault
              inputs.webphone.packages.${pkgs.stdenv.hostPlatform.system}.webphone;
        };
    in
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];

      imports = [
        inputs.treefmt-nix.flakeModule
        inputs.git-hooks-nix.flakeModule
      ];

      flake = {
        nixosModules = {
          telephony = telephonyModule;
          default = telephonyModule;
        };

        nixosConfigurations.pbx = nixpkgs.lib.nixosSystem {
          system = "x86_64-linux";
          modules = [
            self.nixosModules.telephony
            inputs.nix-ssh-config.nixosModules.ssh
            {
              services.ssh-server = {
                enable = true;
                authorizedKeys = builtins.attrValues inputs.nix-ssh-config.sshKeys;
                # Demo convenience (the VM root console autologs in anyway):
                # reach the VM as root with a tracked key. Password auth stays
                # off — drop this line on real deployments. Keys-only (incl.
                # keyboard-interactive) is the module default since upstream
                # v0.1.2; tests/ssh.nix asserts the effective config.
                allowRootLogin = true;
              };
            }
            ./hosts/pbx
          ];
        };

        # Production host template: file-based secrets, ACME TLS, CDR, real
        # disk layout (disko, hosts/pbx-prod/disk.nix). Install with
        # (runbook: docs/deploy.md §4):
        #   nix run github:numtide/nixos-anywhere -- \
        #     --flake .#pbx-prod --target-host root@<server-ip>
        # `nix flake check` evaluates this toplevel, so the template cannot
        # rot silently; it never boots in CI.
        nixosConfigurations.pbx-prod = nixpkgs.lib.nixosSystem {
          system = "x86_64-linux";
          modules = [
            self.nixosModules.telephony
            inputs.nix-ssh-config.nixosModules.ssh
            inputs.disko.nixosModules.disko
            ./hosts/pbx-prod
            ./hosts/pbx-prod/disk.nix
            {
              services.ssh-server = {
                enable = true;
                authorizedKeys = builtins.attrValues inputs.nix-ssh-config.sshKeys;
                # Keys-only is the module default since upstream v0.1.2:
                # passwordAuthentication and the PAM-serviced
                # keyboard-interactive door are both off, asserted in
                # tests/ssh.nix. Root login stays keys-only by the same
                # defaults — PermitRootLogin "yes" here is therefore the
                # prohibit-password posture, which the ops runbook needs
                # (docs/deploy.md: nixos-rebuild --target-host root@<host>).
                allowRootLogin = true;
                allowUsers = [ "root" ];
              };
            }
          ];
        };
      };

      perSystem =
        {
          config,
          pkgs,
          self',
          inputs',
          ...
        }:
        let
          webphonePackage = inputs'.webphone.packages.webphone;
        in
        {
          packages = {
            default = self'.packages.webphone;
            webphone = webphonePackage;
            telephony-operator = pkgs.callPackage ./packages/telephony-operator { };
            freeswitch-sounds = pkgs.callPackage ./packages/sounds.nix { };
            initrd-audit = pkgs.callPackage ./packages/initrd-audit { };
          };

          apps.vm = {
            type = "app";
            # Ephemeral demo VM: nix run .#vm
            program = "${self.nixosConfigurations.pbx.config.system.build.vm}/bin/run-pbx-vm";
            meta.description = "Run the example PBX host as a throwaway QEMU VM";
          };

          # Deliberately outside `checks`: the browser E2E suite adds
          # ~1-2 GB of chromium closure and is debugged separately; run it
          # explicitly with `nix build -L .#telephony-browser`.
          legacyPackages.telephony-browser = pkgs.testers.nixosTest (
            import ./tests/browser.nix { inherit telephonyModule webphonePackage; }
          );

          checks =
            # Eval-only regressions (TLS modes, dial-string escaping) —
            # cheap, no VM boot (see tests/eval.nix).
            (import ./tests/eval.nix {
              inherit nixpkgs pkgs telephonyModule;
            })
            // {
              # Multi-node integration: recordings serving, ITSP gateway,
              # escape hatch (see tests/pbx.nix).
              telephony = pkgs.testers.nixosTest (
                import ./tests/pbx.nix { inherit telephonyModule webphonePackage; }
              );
              # Single-node suites for fast bisect (tests/common.nix fixtures).
              telephony-dialplan = pkgs.testers.nixosTest (
                import ./tests/dialplan.nix { inherit telephonyModule webphonePackage; }
              );
              # CDR visibility for the missed-call failover shape: the
              # voicemail-failover leg must leave Master.csv rows (the
              # caller leg is a real sofia self-INVITE — loopback
              # channels never reach mod_cdr_csv). See
              # tests/cdr-visibility.nix.
              telephony-cdr-visibility = pkgs.testers.nixosTest (
                import ./tests/cdr-visibility.nix { inherit telephonyModule webphonePackage; }
              );
              telephony-webphone = pkgs.testers.runNixOSTest (
                import ./tests/webphone.nix { inherit telephonyModule webphonePackage; }
              );
              # The EMPTY-secret-file honest rejection (config-load
              # crash-loop with the journal signature): the contract that
              # would have caught the 2026-10-01 production outage (see
              # tests/webphone-empty-secret.nix).
              telephony-webphone-empty-secret = pkgs.testers.runNixOSTest (
                import ./tests/webphone-empty-secret.nix { inherit telephonyModule webphonePackage; }
              );
              telephony-tls-turn = pkgs.testers.nixosTest (
                import ./tests/tls-turn.nix { inherit telephonyModule webphonePackage pkgs; }
              );
              # File-based secrets (*File options): store purity, runtime
              # splicing, mixed plain/file modes (see tests/secrets.nix).
              telephony-secrets = pkgs.testers.nixosTest (
                import ./tests/secrets.nix { inherit telephonyModule webphonePackage; }
              );
              # Voicemail deposit/retrieval with real RTP and DTMF
              # (see tests/voicemail.nix + tests/vmclient.py).
              telephony-voicemail = pkgs.testers.nixosTest (
                import ./tests/voicemail.nix { inherit telephonyModule webphonePackage; }
              );
              # Health monitoring: timer unit fails on profile/gateway loss
              # (see tests/monitoring.nix).
              telephony-monitoring = pkgs.testers.nixosTest (
                import ./tests/monitoring.nix { inherit telephonyModule webphonePackage; }
              );
              # Backups + failure alerting: restic round-trip, OnFailure
              # webhook routing through a real HTTP sink (tests/backup.nix).
              telephony-backup = pkgs.testers.nixosTest (
                import ./tests/backup.nix { inherit telephonyModule webphonePackage; }
              );
              # fail2ban SIP jail: repeated auth failures get banned
              # (see tests/fail2ban.nix).
              telephony-fail2ban = pkgs.testers.nixosTest (
                import ./tests/fail2ban.nix { inherit telephonyModule webphonePackage; }
              );
              # Declarative IVR menus: dial, press key, land at destination
              # (see tests/ivr.nix).
              telephony-ivr = pkgs.testers.nixosTest (
                import ./tests/ivr.nix { inherit telephonyModule webphonePackage; }
              );
              # Conference rooms: two legs join, the mix streams to both
              # (see tests/conference.nix).
              telephony-conference = pkgs.testers.nixosTest (
                import ./tests/conference.nix { inherit telephonyModule webphonePackage; }
              );
              # Operator window + phone API: voicemail list/play/delete over
              # HTTP, CDR viewer, health cards, dialplan simulator
              # (see tests/operator.nix).
              telephony-operator = pkgs.testers.nixosTest (
                import ./tests/operator.nix { inherit telephonyModule webphonePackage; }
              );
              # Inbound fax: spandsp loaded, the fax extension answers a
              # G.711 call and runs rxfax with T.38 disabled
              # (see tests/fax.nix).
              telephony-fax = pkgs.testers.nixosTest (
                import ./tests/fax.nix { inherit telephonyModule webphonePackage; }
              );
              # Inbound fax feed: rxfax TIFF -> PDF -> the real webphone
              # /hooks/fax webhook, malformed files stay for retry
              # (see tests/fax-feed.nix).
              telephony-fax-feed = pkgs.testers.runNixOSTest (
                import ./tests/fax-feed.nix { inherit telephonyModule webphonePackage; }
              );
              # Telnyx messaging bridge: receiver logging, inbound
              # message.received -> real webphone row, the 503 retry
              # contract across a webphone restart, the /recent token
              # gate (see tests/messaging.nix).
              telephony-messaging = pkgs.testers.runNixOSTest (
                import ./tests/messaging.nix { inherit telephonyModule webphonePackage; }
              );
              # Time-based ring-group routing: in-window rings, after-hours
              # transfers (see tests/time-routing.nix).
              telephony-time-routing = pkgs.testers.nixosTest (
                import ./tests/time-routing.nix { inherit telephonyModule webphonePackage; }
              );
              # Minimal boot proof, parametrized for KVM-less runners
              # (see tests/boot.nix).
              telephony-boot = pkgs.testers.runNixOSTest (
                import ./tests/boot.nix { inherit telephonyModule webphonePackage; }
              );
              # Doc drift alarm: TODO_LIST rows duplicating
              # FULLY_FUNCTIONAL FEATURES rows, citing docs/status or
              # docs/planning snapshots, or citing paths missing from
              # the tree fail the gate (see tests/drift_alarm.py; the
              # self-test negative-tests every arm first).
              docs-drift =
                pkgs.runCommand "docs-drift-alarm"
                  {
                    meta.description = "Doc drift alarm: TODO rows must agree with FEATURES.md, cite live docs only, and cite existing paths";
                    nativeBuildInputs = [ pkgs.python3 ];
                  }
                  ''
                    python3 ${./tests/drift_alarm.py} --self-test | tee $out
                    python3 ${./tests/drift_alarm.py} ${./TODO_LIST.md} ${./FEATURES.md} ${self} | tee -a $out
                  '';
              # Lock-move guard: a tracked flake input (webphone — the
              # only input riding a moving upstream) whose locked rev is
              # never mentioned in CHANGELOG.md fails the gate. Lock
              # moves landed via the auto-commit daemon twice in one
              # week with no attribution anywhere (the 2026-09-24
              # stale-vendorHash breakage class); this makes them loud.
              # Hermetic over two committed files — the sandboxed check
              # cannot read git history, so it compares flake.lock
              # against CHANGELOG.md the same way docs-drift compares
              # TODO_LIST against FEATURES (see scripts/lock_guard.py;
              # the self-test plants all six failure shapes first).
              lock-guard =
                pkgs.runCommand "lock-move-guard"
                  {
                    meta.description = "Lock-move guard: tracked flake inputs must carry a CHANGELOG attribution for their locked rev";
                    nativeBuildInputs = [ pkgs.python3 ];
                  }
                  ''
                    python3 ${./scripts/lock_guard.py} --self-test | tee $out
                    python3 ${./scripts/lock_guard.py} ${./flake.lock} ${./CHANGELOG.md} | tee -a $out
                  '';
              # Keep-a-Changelog decay as a hermetic check: the pre-commit
              # hook only runs on machines with a healed hook battery (the
              # 2026-09-29 silent-hook-loss class), so the one pure-Python
              # lint over a tracked file also runs in CI (see
              # tests/changelog_headings.py; the self-test plants the
              # duplicate-heading decay first).
              changelog-headings =
                pkgs.runCommand "changelog-headings-check"
                  {
                    meta.description = "CHANGELOG must not repeat a section heading inside one version";
                    nativeBuildInputs = [ pkgs.python3 ];
                  }
                  ''
                    python3 ${./tests/changelog_headings.py} --self-test | tee $out
                    python3 ${./tests/changelog_headings.py} ${./CHANGELOG.md} | tee -a $out
                  '';
              # Archive-marker gate: every scoped item (open-work sections
              # b/c/f/g plus plan Step-2 M-rows) in an ARCHIVED snapshot
              # must carry an inline resolution marker; Step-3 fine rows
              # inherit their parent verdict by convention (see
              # scripts/markers_check.py; self-test plants the misses).
              # The self-test also proves the git-history monotonicity arm
              # (verdict counts may never permanently decrease across a
              # snapshot's history) on a synthetic repo — hence git here;
              # the live sweep part runs without .git and auto-skips it.
              markers-check =
                pkgs.runCommand "markers-check"
                  {
                    meta.description = "Archive-marker gate: scoped items in archived status/planning snapshots must carry inline resolution markers";
                    nativeBuildInputs = [
                      pkgs.git
                      pkgs.python3
                    ];
                  }
                  ''
                    python3 ${./scripts/markers_check.py} --self-test | tee $out
                    python3 ${./scripts/markers_check.py} ${./docs/status/archived} ${./docs/planning/archived} | tee -a $out
                  '';
              # Syntax gate for the browser E2E driver: the suite itself
              # stays outside checks (see legacyPackages.telephony-browser),
              # so a python slip in tests/browser-e2e.py would otherwise
              # only surface ~6 minutes into the VM run.
              browser-e2e-pycompile =
                pkgs.runCommand "browser-e2e-pycompile"
                  {
                    meta.description = "Browser E2E driver must py_compile: syntax slips fail in seconds, not a 6-minute VM run";
                    nativeBuildInputs = [ pkgs.python3 ];
                  }
                  ''
                    python3 -m py_compile ${./tests/browser-e2e.py}
                    touch $out
                  '';
              # Production-shape boot smoke (hosts/pbx-prod template with
              # stubbed secrets and self-signed TLS; see tests/prod-boot.nix).
              telephony-prod-boot = pkgs.testers.runNixOSTest (
                import ./tests/prod-boot.nix {
                  inherit telephonyModule webphonePackage;
                  sshServerModule = inputs.nix-ssh-config.nixosModules.ssh;
                }
              );
              # Hardened SSH server integration (nix-ssh-config input).
              telephony-ssh = pkgs.testers.nixosTest (
                import ./tests/ssh.nix {
                  inherit telephonyModule webphonePackage;
                  sshServerModule = inputs.nix-ssh-config.nixosModules.ssh;
                }
              );
              # NAT advertisement runtime proof: two-NIC topology (router
              # with a 5060 port-forward + PBX behind it); a real call from
              # the OUTER network completes and asserts natAddress lands in
              # Via/Contact/SDP (see tests/nat.nix).
              telephony-nat = pkgs.testers.nixosTest (
                import ./tests/nat.nix { inherit telephonyModule webphonePackage; }
              );
              webphone = self'.packages.webphone;
              format = config.treefmt.build.check self;
            }
            # Initrd driver gate (packages/initrd-audit): the artifact that
            # actually ships to metal is pbx-prod's toplevel initrd (the
            # demo host only boots as a VM, where qemu-vm.nix injects the
            # virtio modules itself). x86_64-only like the host it audits.
            # This is the check that would have caught the 2026-09-14
            # unbootable-first-install (zero virtio drivers in the initrd
            # while every VM suite stayed green).
            // pkgs.lib.optionalAttrs (pkgs.stdenv.hostPlatform.system == "x86_64-linux") {
              initrd-audit =
                pkgs.runCommand "initrd-audit-pbx-prod"
                  {
                    nativeBuildInputs = [ self'.packages.initrd-audit ];
                    meta.description = "pbx-prod initrd carries the cloud platform's storage bus drivers";
                  }
                  ''
                    initrd-audit --platform cloud ${self.nixosConfigurations.pbx-prod.config.system.build.initialRamdisk}/initrd | tee $out
                  '';
              # End-to-end companion to initrd-audit: boots the REAL
              # pbx-prod kernel+initrd against a GPT disk-main-root behind
              # a virtio-scsi-pci HBA (Hetzner's bus) via kexec — proves
              # the by-partlabel root mounts instead of hanging at the
              # 2026-09-14-style root wait (tests/metal-boot.nix).
              telephony-metal-boot = pkgs.testers.runNixOSTest (
                import ./tests/metal-boot.nix {
                  inherit pkgs;
                  prod.toplevel = self.nixosConfigurations.pbx-prod.config.system.build.toplevel;
                  prod.kernel = "${self.nixosConfigurations.pbx-prod.config.system.build.toplevel}/kernel";
                  prod.initrd = "${self.nixosConfigurations.pbx-prod.config.system.build.initialRamdisk}/initrd";
                  prod.params = pkgs.lib.concatStringsSep " " self.nixosConfigurations.pbx-prod.config.boot.kernelParams;
                }
              );
            }
            # aarch64 boot proof for KVM-less hosts (GitHub arm runners): the
            # minimal boot suite without the kvm system feature, run under
            # same-arch TCG. The full webphone suite cannot make it through
            # the test driver's fixed 300s serial-shell connect window under
            # TCG; only exists on aarch64 so the x86_64 gate never builds it.
            // pkgs.lib.optionalAttrs (pkgs.stdenv.hostPlatform.system == "aarch64-linux") {
              telephony-boot-tcg = pkgs.testers.runNixOSTest (
                import ./tests/boot.nix {
                  inherit telephonyModule webphonePackage;
                  kvm = false;
                  slowBoot = true;
                }
              );
            };

          pre-commit.settings = {
            hooks = {
              nixfmt.enable = true;
              # statix/deadnix moved to treefmt programs (checks.format +
              # `nix fmt` autofix); nixfmt stays a commit-time hook because
              # commit-time autofix of formatting is its own value.
              # Not a built-in hook in git-hooks.nix: wrap nixpkgs' gitleaks.
              gitleaks = {
                enable = true;
                name = "gitleaks";
                description = "Scan staged changes for hardcoded secrets";
                entry = "${pkgs.gitleaks}/bin/gitleaks protect --staged --redact";
                pass_filenames = false;
              };
              # Keep-a-Changelog decay: one `### <type>` heading per version.
              changelog-headings = {
                enable = true;
                name = "changelog-headings";
                description = "No repeated section headings inside one CHANGELOG version";
                entry = "${pkgs.python3}/bin/python3 ${./tests/changelog_headings.py} CHANGELOG.md";
                files = "CHANGELOG\\.md$";
                pass_filenames = false;
              };
              # Preventive lock-move tripwire (commit-msg stage): a staged
              # webphone rev move without a relock/lock-bump marker in the
              # message dies at the door — the auto-commit daemon never
              # bypasses hooks, and its heuristic messages never carry the
              # marker, so the FIFTH sweep class (2026-10-07, mid-ritual)
              # becomes a blocked commit instead of an attributed-after-
              # the-fact incident. always_run + pass_filenames: git hands
              # commit-msg hooks the message file path, which a `files`
              # filter would mis-match and pass_filenames=false would
              # strip; the script self-gates on what is staged.
              lock-move-guard = {
                enable = true;
                name = "lock-move-guard";
                description = "Staged tracked-input lock moves need a relock/lock-bump marker in the commit message";
                entry = "${pkgs.python3}/bin/python3 ${./scripts/lock_move_hook.py}";
                stages = [ "commit-msg" ];
                always_run = true;
              };
              # Personal-data gate: real values from the gitignored
              # secrets/scrub-patterns.txt must not reach the tree (use
              # scripts/scrub-check.sh --history before any history surgery).
              scrub-check = {
                enable = true;
                name = "scrub-check";
                description = "Fail when tracked files contain listed personal data";
                entry = "${pkgs.bash}/bin/bash ${./scripts/scrub-check.sh}";
                pass_filenames = false;
              };
            };
          };

          devShells.default = pkgs.mkShellNoCC {
            packages = with pkgs; [
              config.treefmt.build.wrapper
              # Lint binaries BuildFlow orchestrates, pinned to this flake's
              # nixpkgs: without them it falls back to `nix run nixpkgs#X`
              # (registry revision, not the pinned one) — the same formatter
              # version-skew class as the oxfmt/prettier war in .buildflow.yml.
              bandit
              dprint
              lychee
              mypy
              prettier
              ruff
              shellcheck
              vulnix
              python3Packages.vulture
              gh
              nil
              jq
            ];
            # git-hooks.nix's updater strips all hooks and reinstalls, but
            # `pre-commit install` refuses while ANY core.hooksPath is
            # visible — the global ~/.gitconfig points at a nonexistent
            # .githooks, so every config-regenerating `nix develop` entry
            # (any tracked-file edit) left the repo ungated. Hiding only
            # the global config during the updater lets install land in
            # the default .git/hooks (the script unsets the local value
            # itself) and its final line re-anchors local core.hooksPath
            # there, which wins over the broken global .githooks at commit
            # time. Saved/restored so the user's session env is untouched.
            shellHook = ''
              git_config_global_saved="''${GIT_CONFIG_GLOBAL:-}"
              export GIT_CONFIG_GLOBAL=/dev/null
              ${config.pre-commit.installationScript}
              if [ -n "$git_config_global_saved" ]; then
                export GIT_CONFIG_GLOBAL="$git_config_global_saved"
              else
                unset GIT_CONFIG_GLOBAL
              fi
            '';
          };

          treefmt = {
            projectRootFile = "flake.nix";
            programs = {
              nixfmt.enable = true;
              # statix/deadnix as treefmt programs: same lints, same flags
              # as the runCommands + pre-commit hooks they replace — one
              # checks.format gate and `nix fmt` autofix instead of three
              # parallel surfaces. repeated_keys stays disabled because
              # `services` is deliberately assigned in multiple mkIf-split
              # blocks (freeswitch / nginx / coturn activate under different
              # conditions) which cannot be merged into one attrset; the
              # statix.toml ignore/nix_version fields were proven not
              # load-bearing before retiring that file (findings identical
              # with and without them; only `disabled` changed the result).
              statix = {
                enable = true;
                disabled-lints = [ "repeated_keys" ];
              };
              deadnix = {
                enable = true;
                no-lambda-pattern-names = true;
              };
              prettier = {
                enable = true;
                includes = [
                  "packages/telephony-operator/webroot/*.js"
                  "packages/telephony-operator/webroot/*.html"
                  "packages/telephony-operator/webroot/*.css"
                ];
              };
            };
          };
        };
    };
}
