{
  description = "NixOS telephony stack: FreeSWITCH PBX with WebRTC webphone, STUN/TURN, recording, ITSP gateway";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Hardened, post-quantum-ready SSH server for the example host
    # (services.ssh-server) and the tracked operator keys (sshKeys).
    nix-ssh-config = {
      # Pinned to v0.1.3: VM runtime proofs (ML-KEM negotiation, banner,
      # wrong-key rejection), golden sshd -T snapshot, seven new server/
      # client options (listenAddresses, usePam, authenticationMethods,
      # controlMaster, updateHostKeys, certificateFile, LoginGraceTime).
      url = "github:LarsArtmann/nix-ssh-config/v0.1.3";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    flake-parts = {
      url = "github:hercules-ci/flake-parts";
      inputs.nixpkgs-lib.follows = "nixpkgs";
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
      telephonyModule = import ./modules/telephony;
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
            ./hosts/pbx-prod
          ];
        };
      };

      perSystem =
        {
          config,
          pkgs,
          self',
          ...
        }:
        {
          packages = {
            default = self'.packages.webphone;
            webphone = pkgs.callPackage ./packages/webphone { };
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
          legacyPackages.telephony-browser = pkgs.testers.nixosTest (import ./tests/browser.nix);

          checks =
            # Eval-only regressions (TLS modes, dial-string escaping) —
            # cheap, no VM boot (see tests/eval.nix).
            (import ./tests/eval.nix {
              inherit nixpkgs pkgs telephonyModule;
            })
            // {
              # Multi-node integration: recordings serving, ITSP gateway,
              # escape hatch (see tests/pbx.nix).
              telephony = pkgs.testers.nixosTest (import ./tests/pbx.nix);
              # Single-node suites for fast bisect (tests/common.nix fixtures).
              telephony-dialplan = pkgs.testers.nixosTest (import ./tests/dialplan.nix);
              telephony-webphone = pkgs.testers.runNixOSTest (import ./tests/webphone.nix { });
              telephony-tls-turn = pkgs.testers.nixosTest (import ./tests/tls-turn.nix);
              # File-based secrets (*File options): store purity, runtime
              # splicing, mixed plain/file modes (see tests/secrets.nix).
              telephony-secrets = pkgs.testers.nixosTest (import ./tests/secrets.nix);
              # Voicemail deposit/retrieval with real RTP and DTMF
              # (see tests/voicemail.nix + tests/vmclient.py).
              telephony-voicemail = pkgs.testers.nixosTest (import ./tests/voicemail.nix);
              # Health monitoring: timer unit fails on profile/gateway loss
              # (see tests/monitoring.nix).
              telephony-monitoring = pkgs.testers.nixosTest (import ./tests/monitoring.nix);
              # Backups + failure alerting: restic round-trip, OnFailure
              # webhook routing through a real HTTP sink (tests/backup.nix).
              telephony-backup = pkgs.testers.nixosTest (import ./tests/backup.nix);
              # fail2ban SIP jail: repeated auth failures get banned
              # (see tests/fail2ban.nix).
              telephony-fail2ban = pkgs.testers.nixosTest (import ./tests/fail2ban.nix);
              # Declarative IVR menus: dial, press key, land at destination
              # (see tests/ivr.nix).
              telephony-ivr = pkgs.testers.nixosTest (import ./tests/ivr.nix);
              # Conference rooms: two legs join, the mix streams to both
              # (see tests/conference.nix).
              telephony-conference = pkgs.testers.nixosTest (import ./tests/conference.nix);
              # Time-based ring-group routing: in-window rings, after-hours
              # transfers (see tests/time-routing.nix).
              telephony-time-routing = pkgs.testers.nixosTest (import ./tests/time-routing.nix);
              # Minimal boot proof, parametrized for KVM-less runners
              # (see tests/boot.nix).
              telephony-boot = pkgs.testers.runNixOSTest (import ./tests/boot.nix { });
              # Doc drift alarm: TODO_LIST rows duplicating FULLY_FUNCTIONAL
              # FEATURES rows fail the gate (see tests/drift_alarm.py).
              docs-drift =
                pkgs.runCommand "docs-drift-alarm"
                  {
                    meta.description = "Doc drift alarm: no TODO row may re-request a FULLY_FUNCTIONAL feature";
                    nativeBuildInputs = [ pkgs.python3 ];
                  }
                  ''
                    python3 ${./tests/drift_alarm.py} ${./TODO_LIST.md} ${./FEATURES.md} | tee $out
                  '';
              # Production-shape boot smoke (hosts/pbx-prod template with
              # stubbed secrets and self-signed TLS; see tests/prod-boot.nix).
              telephony-prod-boot = pkgs.testers.runNixOSTest (
                import ./tests/prod-boot.nix {
                  sshServerModule = inputs.nix-ssh-config.nixosModules.ssh;
                }
              );
              # Hardened SSH server integration (nix-ssh-config input).
              telephony-ssh = pkgs.testers.nixosTest (
                import ./tests/ssh.nix { sshServerModule = inputs.nix-ssh-config.nixosModules.ssh; }
              );
              webphone = self'.packages.webphone;
              format = config.treefmt.build.check self;
              statix =
                pkgs.runCommand "statix-check"
                  {
                    nativeBuildInputs = [ pkgs.statix ];
                  }
                  ''
                    cd ${self}
                    statix check -o errfmt . 2>&1 | tee $out
                  '';

              deadnix =
                pkgs.runCommand "deadnix-check"
                  {
                    nativeBuildInputs = [ pkgs.deadnix ];
                  }
                  ''
                    cd ${self}
                    deadnix --fail --no-lambda-pattern-names . 2>&1 | tee $out
                  '';
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
            }
            # aarch64 boot proof for KVM-less hosts (GitHub arm runners): the
            # minimal boot suite without the kvm system feature, run under
            # same-arch TCG. The full webphone suite cannot make it through
            # the test driver's fixed 300s serial-shell connect window under
            # TCG; only exists on aarch64 so the x86_64 gate never builds it.
            // pkgs.lib.optionalAttrs (pkgs.stdenv.hostPlatform.system == "aarch64-linux") {
              telephony-boot-tcg = pkgs.testers.runNixOSTest (
                import ./tests/boot.nix {
                  kvm = false;
                  slowBoot = true;
                }
              );
            };

          pre-commit.settings = {
            hooks = {
              nixfmt.enable = true;
              statix.enable = true;
              deadnix.enable = true;
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
              nil
              jq
            ];
            shellHook = config.pre-commit.installationScript;
          };

          treefmt = {
            projectRootFile = "flake.nix";
            programs = {
              nixfmt.enable = true;
              prettier = {
                enable = true;
                includes = [
                  "packages/webphone/assets/*.js"
                  "packages/webphone/assets/*.html"
                  "packages/webphone/assets/*.css"
                ];
              };
            };
          };
        };
    };
}
