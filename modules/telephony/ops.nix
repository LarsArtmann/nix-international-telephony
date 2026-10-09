# Operator tooling: the host shell basics an admin reaches for on first
# ssh — system monitors, network/SIP diagnostics, JSON and database
# inspection — plus a flake-enabled nix CLI. The deploy docs and the ops
# runbook both assume `nix run/shell nixpkgs#<tool>` works on the host:
# without nix-command+flakes every such call dies with "experimental Nix
# feature ... is disabled", and without a pinned registry entry `nixpkgs`
# would resolve to whatever the global flake registry serves that day.
# Pin it to the exact store source this system was evaluated from: no
# channels, no drift, no network for resolution.
#
# (curl, strace and iproute2's ss come with the base system path; fs_cli
# ships with the freeswitch package.)
{
  config,
  lib,
  pkgs,
  ...
}:

let
  cfg = config.services.telephony;

  # The event-socket password argument for the fs_cli wrapper: runtime
  # file when set (read per invocation — a rotation takes effect on the
  # next call, nothing secret lands in the store), else the inline value.
  fsCliPassArg =
    if cfg.eventSocketPasswordFile != null then
      ''"$(cat ${lib.escapeShellArg cfg.eventSocketPasswordFile})"''
    else
      lib.escapeShellArg cfg.eventSocketPassword;
in
{
  config = lib.mkIf (cfg.enable && cfg.opsTools.enable) {
    environment.systemPackages =
      (with pkgs; [
        btop
        htop
        dig
        tcpdump
        jq
        lsof
        sqlite
        tmux
        vim
        openssl
      ])
      ++ lib.optionals config.services.freeswitch.enable [
        # fs_cli with the event-socket password baked in as a RUNTIME
        # read: bare `fs_cli …` works verbatim for operators (the
        # runbook's one-liners) instead of dying in auth against the
        # ClueCon default password. -H 127.0.0.1 is REQUIRED: the
        # builtin profile has an EMPTY host, so a bare call dies
        # "Error Connecting []" (proven against the 1.11.1 binary,
        # 2026-10-08) even with auth settled. hiPrio:
        # /run/current-system/sw/bin would otherwise be a same-priority
        # collision with the freeswitch package's own fs_cli — the
        # wrapper wins deterministically and the unwrapped binary stays
        # reachable at ${config.services.freeswitch.package}/bin/fs_cli.
        (lib.hiPrio (
          pkgs.writeShellScriptBin "fs_cli" ''
            exec ${config.services.freeswitch.package}/bin/fs_cli -H 127.0.0.1 -p ${fsCliPassArg} "$@"
          ''
        ))
      ];

    nix.settings.experimental-features = [
      "nix-command"
      "flakes"
    ];
    # The pinned entry drags the nixpkgs SOURCE tree (~200 MiB) into the
    # closure via /etc/nix/registry.json — opt-outable for appliance
    # images that never run ad-hoc `nixpkgs#` tools (opsTools.embedNixpkgsRegistry).
    #
    # BUG FIXED 2026-10-09: the mkIf below alone was a NO-OP for the
    # closure — nixpkgs ITSELF registers the same entry via
    # nixpkgs.flake.setFlakeRegistry (mkDefault, nixos/modules/misc/
    # nixpkgs-flake.nix), and a disabled duplicate definition cannot
    # beat that default: consumers flipping the option off kept the
    # ~200 MiB source. The kill must go through nixpkgs' own knob, and
    # setNixPath has to fall with it (the module asserts
    # setNixPath -> setFlakeRegistry at eval).
    nix.registry.nixpkgs.to = lib.mkIf cfg.opsTools.embedNixpkgsRegistry {
      type = "path";
      inherit (pkgs) path;
    };
    nixpkgs.flake.setFlakeRegistry = lib.mkIf (!cfg.opsTools.embedNixpkgsRegistry) false;
    nixpkgs.flake.setNixPath = lib.mkIf (!cfg.opsTools.embedNixpkgsRegistry) false;

    # Eval-time contract for the flip (both directions): the entry is
    # pinned when enabled and effectively gone when disabled. The
    # disabled arm is what would have caught the setFlakeRegistry
    # no-op bug above at eval time instead of at a closure-size audit.
    assertions = [
      {
        assertion = cfg.opsTools.embedNixpkgsRegistry -> (config.nix.registry.nixpkgs.to or { }) != { };
        message = "services.telephony.opsTools.embedNixpkgsRegistry: enabled but the nixpkgs registry entry resolved empty — the pinned-source pin is being defeated.";
      }
      {
        assertion =
          !cfg.opsTools.embedNixpkgsRegistry
          -> !(
            (config.nix.registry.nixpkgs.to or null) != null && (config.nix.registry.nixpkgs.to or { }) != { }
          );
        message = "services.telephony.opsTools.embedNixpkgsRegistry: disabled but the nixpkgs registry entry is still populated — the ~200 MiB nixpkgs source stays in the closure (nixpkgs.flake.setFlakeRegistry interplay).";
      }
    ];
    # Kill the global flake registry: nix eagerly downloads it when
    # resolving ANY indirect ref, and a failed download (offline host,
    # VM test net) aborts the whole lookup even though the pinned
    # system entry above matches. With it gone, `nixpkgs` resolves
    # purely locally to the pinned source.
    nix.settings.flake-registry = "";
    # Route legacy <nixpkgs> lookups (e.g. `nix-shell -p` without flake
    # syntax) through the pinned registry entry above.
    nix.settings.nix-path = [ "nixpkgs=flake:nixpkgs" ];
  };
}
