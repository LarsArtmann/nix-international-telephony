{
  description = "NixOS telephony stack: FreeSWITCH PBX with WebRTC webphone, STUN/TURN, recording, ITSP gateway";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

    # Hardened, post-quantum-ready SSH server for the example host
    # (services.ssh-server) and the tracked operator keys (sshKeys).
    nix-ssh-config = {
      url = "github:LarsArtmann/nix-ssh-config";
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
                # off — drop this line on real deployments.
                allowRootLogin = true;
                # NixOS defaults KbdInteractiveAuthentication to yes, and
                # with UsePAM the keyboard-interactive prompts accept Unix
                # account passwords — PasswordAuthentication no alone is not
                # keys-only (the demo root has an initialPassword).
                extraSettings.KbdInteractiveAuthentication = false;
              };
            }
            ./hosts/pbx
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
          };

          apps.vm = {
            type = "app";
            # Ephemeral demo VM: nix run .#vm
            program = "${self.nixosConfigurations.pbx.config.system.build.vm}/bin/run-pbx-vm";
            meta.description = "Run the example PBX host as a throwaway QEMU VM";
          };

          checks = {
            # Multi-node integration: recordings serving, ITSP gateway,
            # escape hatch (see tests/pbx.nix).
            telephony = pkgs.testers.nixosTest (import ./tests/pbx.nix);
            # Single-node suites for fast bisect (tests/common.nix fixtures).
            telephony-dialplan = pkgs.testers.nixosTest (import ./tests/dialplan.nix);
            telephony-webphone = pkgs.testers.nixosTest (import ./tests/webphone.nix);
            telephony-tls-turn = pkgs.testers.nixosTest (import ./tests/tls-turn.nix);
            # Browser E2E: two chromium instances do a real WebRTC call
            # through the wss proxy (adds ~1-2 GB of closure).
            telephony-browser = pkgs.testers.nixosTest (import ./tests/browser.nix);
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
