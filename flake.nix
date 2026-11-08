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

    # The pbx-lens call-history index (extracted 2026-10-11): a single Go
    # binary reading the stack's CDR CSV, webhook JSONL and transcripts;
    # its deploy surface lives in modules/telephony/lens.nix. Tracks main;
    # the exact revision lives in flake.lock only.
    pbx-lens = {
      url = "github:LarsArtmann/pbx-lens";
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
          services.telephony.pbx-lens.package =
            lib.mkDefault
              inputs.pbx-lens.packages.${pkgs.stdenv.hostPlatform.system}.default;
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
        # The FreeSWITCH XML generator as a plain library output:
        # `flake.lib.telephony.mkFreeSwitchConfig { lib, pkgs }` returns
        # the settings -> configDir-overlay function from
        # modules/freeswitch.nix, evaluable without instantiating a whole
        # nixosSystem (the dialplan-sim check rides this; consumers like
        # documentation tooling or future stack reusers can inspect the
        # generated XML directly).
        lib.telephony.mkFreeSwitchConfig = import ./modules/freeswitch.nix;

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

          apps.check-vm = {
            type = "app";
            # Sequential VM-suite driver: `nix flake check` builds every
            # check concurrently, and ~10 concurrent VM boots saturated
            # one host badly enough to break a suite's pipe mid-run (the
            # 2026-10-12 messaging broken-pipe flake; green on solo
            # rerun) — and on a 7 GB hosted CI runner it KILLED the
            # runner outright ("hosted runner lost communication",
            # twin 1h deaths 42408682023 / 42409757572, both mid
            # flake-check with every VM suite building at once). This app
            # runs the same VM suites ONE at a time, each bounded by its
            # own budget (CHECK_VM_TIMEOUT seconds, default 45 min) so a
            # wedged suite fails loudly instead of starving the job:
            #   nix run .#check-vm                        # all VM suites
            #   nix run .#check-vm -- telephony-webphone  # a subset
            # VM suites are the derivations named vm-test-run-*, discovered
            # at eval so the list never drifts from checks.
            meta.description = "Run every VM suite sequentially (local flake-check driver; avoids concurrent-VM host pressure)";
            program = pkgs.lib.getExe (
              pkgs.writeShellScriptBin "check-vm" ''
                set -euo pipefail
                system=${pkgs.stdenv.hostPlatform.system}
                if [ "''${1:-}" = "--system" ]; then system="$2"; shift 2; fi
                if [ "$#" -gt 0 ]; then
                  suites="$*"
                else
                  suites=$(nix eval ".#checks.$system" --raw --apply '
                    checks:
                    builtins.concatStringsSep " " (
                      builtins.filter
                        (
                          n:
                          builtins.match "vm-test-run-.*" (checks.''${n}.name or "") != null
                        )
                        (builtins.attrNames checks)
                    )
                  ')
                fi
                if [ -z "$suites" ]; then
                  echo "check-vm: no VM suites found in .#checks.$system" >&2
                  exit 1
                fi
                rc=0
                for suite in $suites; do
                  echo "=== $suite ==="
                  if ! timeout "''${CHECK_VM_TIMEOUT:-2700}" nix build -L ".#checks.$system.$suite" --no-link; then
                    echo "FAILED: $suite"
                    rc=1
                  fi
                done
                exit $rc
              ''
            );
          };

          # Deliberately outside `checks` (chromium closures / the
          # solo-browser rule / full-demo boot cost): the on-demand VM
          # lanes as one table, comments at their rows. The plain rows
          # ride the same one-line shape as checks.plainSuites;
          # demo-wallclock's extra ssh args stay explicit. A/B-proven
          # drvPath-stable against the pre-table wiring (2026-11-08).
          legacyPackages =
            let
              legacySuite =
                file:
                pkgs.testers.nixosTest (
                  import file {
                    inherit telephonyModule webphonePackage;
                  }
                );
            in
            {
              # The browser E2E suite adds ~1-2 GB of chromium closure and
              # is debugged separately; run it explicitly with
              #   nix build -L .#telephony-browser
              telephony-browser = legacySuite ./tests/browser.nix;
              # Boots the FULL demo host (agent, lens, messaging, backups)
              # as a wall-clock smoke. Run:
              #   nix build -L .#telephony-demo-wallclock
              telephony-demo-wallclock = pkgs.testers.nixosTest (
                import ./tests/demo-wallclock.nix {
                  inherit telephonyModule webphonePackage;
                  sshModule = inputs.nix-ssh-config.nixosModules.ssh;
                  sshKeys = builtins.attrValues inputs.nix-ssh-config.sshKeys;
                }
              );
              # The passkey ceremony E2E carries a chromium closure and
              # runs SOLO (browser rule).
              #   nix build -L .#telephony-passkey
              telephony-passkey = legacySuite ./tests/passkey.nix;
              # The theme-ONLY slice of the browser E2E (THEME_ONLY=1 gates
              # browser-e2e.py's main): the fast relock-ritual lane for
              # markup/theme deltas — one browser, no call, minutes. Run:
              #   nix build -L .#telephony-theme
              # Its green never substitutes for the full suite's.
              telephony-theme = legacySuite ./tests/theme-e2e.nix;
            };

          checks =
            let
              # One row per VM suite taking the plain closure. The row
              # names the tester (nixosTest vs runNixOSTest is
              # load-bearing: runNixOSTest accepts the KVM-less TCG
              # arguments, legacy nixosTest rejects them) and the suite
              # file; every comment stays at its row. Adding a plain
              # suite is one row here. A/B-proven byte-identical
              # drvPaths against the pre-table wiring (2026-11-08: the
              # vm-test-run derivations are value-level, so they are
              # stable under flake.nix edits — only checks embedding
              # ${self}, like format/doc-counts, move).
              plainSuite =
                tester: file:
                tester (
                  import file {
                    inherit telephonyModule webphonePackage;
                  }
                );
              plainSuites = {
                # Multi-node integration: recordings serving, ITSP gateway,
                # escape hatch (see tests/pbx.nix).
                telephony = plainSuite pkgs.testers.nixosTest ./tests/pbx.nix;
                # Single-node suites for fast bisect (tests/common.nix fixtures).
                telephony-dialplan = plainSuite pkgs.testers.nixosTest ./tests/dialplan.nix;
                # CDR visibility for the missed-call failover shape: the
                # voicemail-failover leg must leave Master.csv rows (the
                # caller leg is a real sofia self-INVITE — loopback
                # channels never reach mod_cdr_csv). See
                # tests/cdr-visibility.nix.
                telephony-cdr-visibility = plainSuite pkgs.testers.nixosTest ./tests/cdr-visibility.nix;
                telephony-webphone = plainSuite pkgs.testers.runNixOSTest ./tests/webphone.nix;
                # Dynamic SIP directory (credential brokering): derived
                # credentials register, wrong/revoked ones do not, the
                # static fallback still does (tests/webphone-dynamic-directory.nix).
                telephony-webphone-dynamic-directory = plainSuite pkgs.testers.runNixOSTest ./tests/webphone-dynamic-directory.nix;
                # The EMPTY-secret-file honest rejection (config-load
                # crash-loop with the journal signature): the contract that
                # would have caught the 2026-10-01 production outage (see
                # tests/webphone-empty-secret.nix).
                telephony-webphone-empty-secret = plainSuite pkgs.testers.runNixOSTest ./tests/webphone-empty-secret.nix;
                # File-based secrets (*File options): store purity, runtime
                # splicing, mixed plain/file modes (see tests/secrets.nix).
                telephony-secrets = plainSuite pkgs.testers.nixosTest ./tests/secrets.nix;
                # Voicemail deposit/retrieval with real RTP and DTMF
                # (see tests/voicemail.nix + tests/vmclient.py).
                telephony-voicemail = plainSuite pkgs.testers.nixosTest ./tests/voicemail.nix;
                # Health monitoring: timer unit fails on profile/gateway loss
                # (see tests/monitoring.nix).
                telephony-monitoring = plainSuite pkgs.testers.nixosTest ./tests/monitoring.nix;
                # Backups + failure alerting: restic round-trip, OnFailure
                # webhook routing through a real HTTP sink (tests/backup.nix).
                telephony-backup = plainSuite pkgs.testers.nixosTest ./tests/backup.nix;
                # fail2ban SIP jail: repeated auth failures get banned
                # (see tests/fail2ban.nix).
                telephony-fail2ban = plainSuite pkgs.testers.nixosTest ./tests/fail2ban.nix;
                # Declarative IVR menus: dial, press key, land at destination
                # (see tests/ivr.nix).
                telephony-ivr = plainSuite pkgs.testers.nixosTest ./tests/ivr.nix;
                # AI voice agent end to end against a loopback stub:
                # park, greet, one turn, [ACTION: end] hangup, transcript +
                # recording evidence (see tests/agent.nix).
                telephony-agent = plainSuite pkgs.testers.nixosTest ./tests/agent.nix;
                # The pbx-lens call-history index against the REAL stack:
                # CDR ingest through the ro-bind/ACL read path, the 2s poll
                # cadence carrying a fresh Master.csv row into
                # /api/export.jsonl, and a verified snapshot staged
                # (see tests/lens.nix; access wiring + state.* registration
                # are asserted eval-only in tests/eval.nix).
                telephony-lens = plainSuite pkgs.testers.nixosTest ./tests/lens.nix;
                # Register=false trunk shape: NOREG state, zero REGISTERs,
                # and per-call digest auth on outbound INVITEs through a
                # scripted fake ITSP (see tests/noreg-gateway.nix).
                telephony-noreg-gateway = plainSuite pkgs.testers.nixosTest ./tests/noreg-gateway.nix;
                # TCP trunk shape: host:port;transport=tcp passes the
                # gateway-challenge anti-spoof check that a bare
                # ";transport=tcp" suffix fails (see tests/noreg-gateway-tcp.nix).
                telephony-noreg-gateway-tcp = plainSuite pkgs.testers.nixosTest ./tests/noreg-gateway-tcp.nix;
                # FS TLS provisioning: boot render, DynamicUser ownership,
                # hash-guarded redundant fires, and the renewal path —
                # PathChanged -> re-render -> freeswitch restart (see
                # tests/fs-cert-renewal.nix).
                telephony-fs-cert-renewal = plainSuite pkgs.testers.nixosTest ./tests/fs-cert-renewal.nix;
                # Conference rooms: two legs join, the mix streams to both
                # (see tests/conference.nix).
                telephony-conference = plainSuite pkgs.testers.nixosTest ./tests/conference.nix;
                # Operator window + phone API: voicemail list/play/delete over
                # HTTP, CDR viewer, health cards, dialplan simulator
                # (see tests/operator.nix).
                telephony-operator = plainSuite pkgs.testers.nixosTest ./tests/operator.nix;
                # Forward-auth mode RETIRED (2026-10-29, native-OAuth phase 1:
                # the oauth2-proxy gates are deleted from the only consumer
                # deployment, authMode "oidc" is the native path — the mode,
                # its options and this VM test died together; the shape is
                # preserved in git history).
                # Native-OAuth recordings mode: the telephony-recordings-view
                # app owns its own OIDC login (PKCE + signed sessions) behind
                # a dumb nginx proxy — the whole browser dance driven from the
                # client node against a loopback stub IdP, group gate
                # fail-closed (see tests/native-oidc-recordings.nix).
                telephony-native-oidc-recordings = plainSuite pkgs.testers.nixosTest ./tests/native-oidc-recordings.nix;
                # Inbound fax: spandsp loaded, the fax extension answers a
                # G.711 call and runs rxfax with T.38 disabled
                # (see tests/fax.nix).
                telephony-fax = plainSuite pkgs.testers.nixosTest ./tests/fax.nix;
                # Inbound fax feed: rxfax TIFF -> PDF -> the real webphone
                # /hooks/fax webhook, malformed files stay for retry
                # (see tests/fax-feed.nix).
                telephony-fax-feed = plainSuite pkgs.testers.runNixOSTest ./tests/fax-feed.nix;
                # Telnyx messaging bridge: receiver logging, inbound
                # message.received -> real webphone row, the 503 retry
                # contract across a webphone restart, the /recent token
                # gate (see tests/messaging.nix).
                telephony-messaging = plainSuite pkgs.testers.runNixOSTest ./tests/messaging.nix;
                # Supervised text agent: receiver JSONL -> tailer (through
                # the ro bind + ACL path) -> Gemini-stub draft -> review
                # approve over the REAL outbound gateway into the stub
                # Telnyx; STOP suppression gate (see tests/textagent.nix).
                telephony-textagent = plainSuite pkgs.testers.runNixOSTest ./tests/textagent.nix;
                # Time-based ring-group routing: in-window rings, after-hours
                # transfers (see tests/time-routing.nix).
                telephony-time-routing = plainSuite pkgs.testers.nixosTest ./tests/time-routing.nix;
                # Minimal boot proof, parametrized for KVM-less runners
                # (see tests/boot.nix).
                telephony-boot = plainSuite pkgs.testers.runNixOSTest ./tests/boot.nix;
                # NAT advertisement runtime proof: two-NIC topology (router
                # with a 5060 port-forward + PBX behind it); a real call from
                # the OUTER network completes and asserts natAddress lands in
                # Via/Contact/SDP (see tests/nat.nix).
                telephony-nat = plainSuite pkgs.testers.nixosTest ./tests/nat.nix;
              };
            in
            # Eval-only regressions (TLS modes, dial-string escaping) —
            # cheap, no VM boot (see tests/eval.nix).
            (import ./tests/eval.nix {
              inherit nixpkgs pkgs telephonyModule;
            })
            // plainSuites
            // {
              # Manual-TLS + TURN proof: needs pkgs for the cert tooling
              # (see tests/tls-turn.nix).
              telephony-tls-turn = pkgs.testers.nixosTest (
                import ./tests/tls-turn.nix {
                  inherit telephonyModule webphonePackage pkgs;
                }
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
                    # git rides along because lock_move_hook.py's self-test
                    # builds a synthetic repo (its arms are real git
                    # plumbing operations).
                    nativeBuildInputs = [
                      pkgs.python3
                      pkgs.git
                    ];
                    # tracked_inputs.py is the single TRACKED_INPUTS home
                    # (scripts/lock_guard.py imports it; the commit-msg
                    # hook resolves it via its own directory).
                    PYTHONPATH = "${./scripts}";
                  }
                  ''
                    python3 ${./scripts/lock_guard.py} --self-test | tee $out
                    python3 ${./scripts/lock_guard.py} ${./flake.lock} ${./CHANGELOG.md} | tee -a $out
                    # The commit-msg stage's own arms ride the same check
                    # (2026-11-07): the hook lane ran lock_move_hook.py's
                    # self-test while the check lane only ran lock_guard's
                    # — a hook regression would have been invisible to
                    # CI until a real lock move slipped through.
                    python3 ${./scripts/lock_move_hook.py} --self-test | tee -a $out
                  '';
              # Doc-counts: the living docs' count literals (FEATURES "49
              # flake checks", AGENTS "344 stdlib tests") re-derive from
              # the tree — count drift fails the gate instead of rotting
              # the numbers (the docs-health BUILD rule, wired 2026-11-07).
              # The check counts its sibling checks NATIVELY (attrNames
              # forces keys, not values — no recursion with this member)
              # because a sandboxed check cannot run `nix eval`; the
              # stdlib count re-derives via unittest discovery over the
              # flake's own clean source (${self}) — the test modules
              # import repo-relative context at module level, so the
              # whole source tree is the only honest repo-root.
              doc-counts =
                pkgs.runCommand "doc-counts"
                  {
                    meta.description = "Doc count claims must match the derived tree counts";
                    nativeBuildInputs = [ pkgs.python3 ];
                    checkCount = builtins.length (builtins.attrNames self'.checks);
                    src = self;
                  }
                  ''
                    python3 ${./scripts/doc_counts.py} \
                      --repo-root "$src" \
                      --check-count "$checkCount" \
                      | tee $out
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
              # Marker-gate REGRESSION suite: the pytest module ports the
              # load-bearing arms into a second lane (the scripts' own
              # --self-test arms run above), including the ID-header
              # regression, the count-preserving evasion class in
              # pure-function form, exit-code/docstring parity, and the
              # incident triangle (CHANGELOG <-> lesson <-> AGENTS.md).
              markers-test =
                pkgs.runCommand "markers-test"
                  {
                    meta.description = "Marker-gate regression suite: markers_check + rendering_audit arms and the incident triangle";
                    nativeBuildInputs = [
                      pkgs.git
                      pkgs.python3
                    ];
                  }
                  ''
                    GATE_REPO_ROOT=${self} python3 ${./tests/test_markers_check.py} | tee $out
                  '';
              # Rendering audit: the damage class the marker gates cannot
              # see (line-start ~~~ fences, unclosed fences, strikes open
              # at paragraph boundaries, odd ** parity in table rows);
              # --repo-root points the incident triangle at the source
              # tree (cwd is the empty build dir in the sandbox).
              rendering-audit =
                pkgs.runCommand "rendering-audit"
                  {
                    meta.description = "Rendering audit over archived snapshots plus the incident-triangle and split-brain assertions";
                    nativeBuildInputs = [ pkgs.python3 ];
                  }
                  ''
                    python3 ${./scripts/rendering_audit.py} --self-test | tee $out
                    python3 ${./scripts/rendering_audit.py} --repo-root ${self} ${./docs/status/archived} ${./docs/planning/archived} | tee -a $out
                  '';
              # Archive-time checklist: the annotate -> gate -> move
              # ordering as the only path (content gate BEFORE git mv,
              # post-move gates after); the self-test proves both the
              # refusal arm (unmarked snapshot never moves) and the
              # green path on a synthetic repo — hence git.
              archive-checklist =
                pkgs.runCommand "archive-checklist"
                  {
                    meta.description = "Archive-time checklist: annotate, gate, then move — mechanically ordered";
                    nativeBuildInputs = [
                      pkgs.git
                      pkgs.python3
                    ];
                  }
                  ''
                    GATE_SCRIPTS_DIR=${./scripts} python3 ${./scripts/archive_snapshot.py} --self-test | tee $out
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
              # EventCatalog exporter golden selftest: the exporter's
              # output contract (determinism, idempotence, isolated
              # refs, --plain parity) ran only on authoring machines
              # until this wiring — the renderer stays stdlib-Python by
              # hub contract (the hub runner has no nix), so Nix owns
              # the regression lane, not the rendering
              # (see scripts/export-catalog.py).
              catalog-export =
                pkgs.runCommand "catalog-export-selftest"
                  {
                    meta.description = "EventCatalog exporter golden selftest: deterministic, idempotent, isolated refs";
                    nativeBuildInputs = [ pkgs.python3 ];
                    PYTHONPATH = "${./scripts}";
                  }
                  ''
                    python3 ${./scripts/export-catalog.py} --selftest | tee $out
                  '';
              # Hermetic dialplan dry-run: the operator VM suite proves
              # the simulator against a booted stack in minutes; this
              # check renders the SAME generated dialplan XML through
              # flake.lib.telephony.mkFreeSwitchConfig (the pure
              # generator behind modules/telephony/pbx.nix) and
              # dry-runs the routing semantics in build-seconds. The
              # fixture spells out every gateway/IVR/conference field
              # with the option defaults' values, so the XML matches
              # what an equivalently configured host serves.
              dialplan-sim =
                let
                  mkFsConfig = import ./modules/freeswitch.nix {
                    inherit (pkgs) lib;
                    inherit pkgs;
                  };
                  simFixture = mkFsConfig {
                    domain = "sim.test";
                    eventSocketPassword = "sim-es-fixture";
                    extensions = {
                      "1000" = {
                        password = "sim-ext-1000";
                        displayName = "Alice";
                        allowInternational = false;
                        vmPassword = "1000";
                      };
                      "1001" = {
                        password = "sim-ext-1001";
                        displayName = "Bob";
                        allowInternational = true;
                        vmPassword = "1001";
                      };
                    };
                    ringGroups."2000" = {
                      members = [
                        "1000"
                        "1001"
                      ];
                      timeoutSec = 25;
                      voicemailMember = "1000";
                      timeWindow = {
                        days = [
                          "mon"
                          "tue"
                          "wed"
                          "thu"
                          "fri"
                        ];
                        startHour = 9;
                        endHour = 17;
                        afterHoursDestination = "9196";
                      };
                    };
                    gateways.demo = {
                      proxy = "sip.example.org";
                      realm = "sip.example.org";
                      username = "simuser";
                      password = "sim-gw-fixture";
                      register = false;
                      retrySeconds = null;
                      priority = 10;
                      allowedCidrs = [ "203.0.113.0/24" ];
                      callerIdNumber = "441632960961";
                      dialPrefix = "+";
                      did = "441632960961";
                      didDestination = "2000";
                      fromUser = null;
                      fromDomain = null;
                      gwAuthAcl = null;
                      inviteIdentityHeader = false;
                      extraInviteHeaders = { };
                      faxDid = null;
                    };
                    ivrs.main = {
                      extension = "4000";
                      greetingSound = "custom/ivr/greeting.wav";
                      invalidSound = "custom/ivr/invalid.wav";
                      timeoutSec = 5;
                      maxTries = 3;
                      entries = {
                        "1".destination = "1000";
                        "2".destination = "2000";
                      };
                      fallbackDestination = "9196";
                    };
                    conferences.room = {
                      extension = "3000";
                      profile = "default";
                      pin = "1234";
                    };
                  };
                in
                pkgs.runCommand "dialplan-sim"
                  {
                    meta.description = "Dialplan dry-run: routing semantics of the generated XML prove in build-seconds, not VM-minutes";
                    nativeBuildInputs = [ self'.packages.telephony-operator ];
                    dialplanDefault = simFixture."dialplan/default.xml";
                    dialplanPublic = simFixture."dialplan/public.xml";
                  }
                  ''
                    mkdir -p dialplan lanes
                    ln -s "$dialplanDefault" dialplan/default.xml
                    ln -s "$dialplanPublic" dialplan/public.xml

                    # Tuesdays: wday 3, inside and outside the 9-17 window.
                    telephony-dialplan-simulate dialplan \
                      --dest 2000 --when 2026-11-10T09:30 > lanes/in-window.txt
                    telephony-dialplan-simulate dialplan \
                      --dest 9196 --when 2026-11-10T09:30 > lanes/echo.txt
                    telephony-dialplan-simulate dialplan \
                      --dest 2000 --when 2026-11-10T21:30 > lanes/after-hours.txt
                    # Inbound DID: the public context transfers to the
                    # ring group, which rings in-window.
                    telephony-dialplan-simulate dialplan \
                      --dest 441632960961 --when 2026-11-10T09:30 > lanes/did.txt
                    # International gate: default directory vars carry
                    # international toll_allow -> the LCR bridge fires;
                    # a domestic-only caller hits the denial leg.
                    telephony-dialplan-simulate dialplan \
                      --dest 4915112345678 > lanes/pstn-allowed.txt
                    telephony-dialplan-simulate dialplan --no-default-vars \
                      --var toll_allow=domestic,local \
                      --dest 4915112345678 > lanes/pstn-denied.txt
                    # IVR menu: entry at the menu app with the fed digit
                    # (menu-entry routing lives in ivr.conf.xml, runtime
                    # territory — the sim records the input honestly).
                    telephony-dialplan-simulate dialplan \
                      --dest 4000 --ivr-input 2 > lanes/ivr.txt
                    # Conference room join.
                    telephony-dialplan-simulate dialplan \
                      --dest 3000 > lanes/conference.txt

                    cat lanes/*.txt | tee $out

                    # In-window: the group bridge rings BOTH members (the
                    # human trace records transfers only; the outcome
                    # lines carry the bridge targets).
                    grep -q '=> ring 1000' lanes/in-window.txt
                    grep -q '=> ring 1001' lanes/in-window.txt
                    # Echo test answers with the echo application.
                    grep -q '"type": "echo"' lanes/echo.txt
                    # After-hours: the time condition fails and the call
                    # transfers to the echo-test destination.
                    grep -q -- '- transfer 9196 XML default' lanes/after-hours.txt
                    grep -q '"type": "echo"' lanes/after-hours.txt
                    # DID: public context -> ring group, ringing in-window.
                    grep -q -- '- transfer 2000 XML default' lanes/did.txt
                    grep -q '=> ring 1001' lanes/did.txt
                    # International allowed by default toll_allow: the
                    # call bridges out through the gateway (LCR).
                    grep -q '=> PSTN <dialed> via demo' lanes/pstn-allowed.txt
                    # Domestic-only toll_allow: the denial leg hangs up.
                    grep -q '"type": "hangup"' lanes/pstn-denied.txt
                    grep -q 'call_rejected' lanes/pstn-denied.txt
                    # IVR: the menu app answers with the fed digit.
                    grep -q '=> IVR menu main (input: 2)' lanes/ivr.txt
                    # Conference: the named room.
                    grep -q '"type": "conference"' lanes/conference.txt
                    grep -q '"room": "room"' lanes/conference.txt
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
              # git-hooks.nix HAS a built-in gitleaks hook at this pin: its
              # default args carry the modern CLI shape (`git --pre-commit
              # ...`), and overriding only `entry` merges OUR old-style
              # entry with THOSE args -> `gitleaks protect ... --pre-commit`
              # -> "unknown flag" + usage dump + exit 126 (the CI red since
              # 2026-10-15). Pin args empty so the proven staged scan runs
              # verbatim.
              gitleaks = {
                enable = true;
                name = "gitleaks";
                description = "Scan staged changes for hardcoded secrets";
                entry = "${pkgs.gitleaks}/bin/gitleaks protect --staged --redact";
                args = [ ];
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
                # The wrapper carries PYTHONPATH so the store copy can
                # import its tracked_inputs sibling (the lone-file store
                # path left the import unresolvable — the 2026-11-07
                # commit-msg breakage the self-heal canary class
                # documents).
                entry = "${pkgs.writeShellScript "lock-move-guard-entry" ''
                  export PYTHONPATH="${./scripts}"
                  exec "${pkgs.python3}/bin/python3" ${./scripts/lock_move_hook.py} "$@"
                ''}";
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
              python3Packages.pytest
              python3Packages.pyupgrade
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
              # conditions) which cannot be merged into one attrset. The
              # repo-root statix.toml (restored 2026-10-12; only
              # `disabled` is load-bearing — ignore/nix_version proven
              # inert) carries the same disable for direct `statix check`
              # runs, which never see this treefmt config.
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
