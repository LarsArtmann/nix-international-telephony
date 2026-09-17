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
in
{
  config = lib.mkIf (cfg.enable && cfg.opsTools.enable) {
    environment.systemPackages = with pkgs; [
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
    ];

    nix.settings.experimental-features = [
      "nix-command"
      "flakes"
    ];
    nix.registry.nixpkgs.to = {
      type = "path";
      inherit (pkgs) path;
    };
    # Kill the global flake registry: nix eagerly downloads it when
    # resolving ANY indirect ref, and a failed download (offline host,
    # VM test net) aborts the whole lookup even though the pinned
    # system entry above matches. With it gone, `nixpkgs` resolves
    # purely locally to the pinned source.
    nix.settings.flake-registry = "";
    # Route legacy <nixpkgs> lookups (e.g. `nix-shell -p` without flake
    # syntax) through the pinned registry entry above.
    nix.nixPath = [ "nixpkgs=flake:nixpkgs" ];
  };
}
