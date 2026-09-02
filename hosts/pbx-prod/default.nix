# Production deployment host: everything the demo VM (hosts/pbx) is not —
# disk-based (disko layout in disk.nix), file-based secrets only, ACME TLS,
# CDR.
#
# Deploy it (see docs/deploy.md for the full runbook):
#   nix run github:numtide/nixos-anywhere -- --flake .#pbx-prod --target-host root@<ip>
#
# Placeholders you MUST fill before installing (all marked CHANGEME):
#   1. tls.acmeEmail (domain is set: pbx.artmann.tech — DNS must point here)
#   2. secrets: render the files referenced below (docs/deploy.md §3;
#      sops-nix recipe in docs/secrets.md) or point secretsDir at your own
#      runtime directory
#   3. the ITSP gateway block (commented out until you have a provider)
# Disk/bootloader for the Hetzner cx22 target live in disk.nix (disko) and
# boot.loader.grub below; UEFI hosts would want systemd-boot instead.
_:

let
  # Single knob for where runtime secrets live. sops-nix renders to
  # /run/secrets/<name> at activation (docs/secrets.md); for manual
  # provisioning use a persistent directory instead (docs/deploy.md §3,
  # Option B — this host's choice: survives reboots, root-only perms).
  secretsDir = "/var/lib/telephony-secrets";
in
{
  networking.hostName = "pbx";
  networking.domain = "artmann.tech";

  # Hetzner Cloud (hel1): DHCP serves IPv4 on ens3; IPv6 is static from
  # the assigned /64 with the standard fe80::1 gateway (console shows
  # 2a01:4f9:c015:c081::/64). Keeps the AAAA record honest.
  networking.interfaces.ens3.ipv6.addresses = [
    {
      address = "2a01:4f9:c015:c081::1";
      prefixLength = 64;
    }
  ];
  networking.defaultGateway6 = {
    address = "fe80::1";
    interface = "ens3";
  };

  # Root filesystem AND grub's boot disk come from disk.nix via disko
  # (ext4 on /dev/sda, GPT + BIOS-boot partition; disko derives
  # boot.loader.grub.devices from the EF02 partition, so no manual entry
  # here — a manual one trips the mirroredBoots duplicate assertion).
  # Hetzner Cloud disks are virtio-scsi (/dev/sda, not /dev/vda).

  services.telephony = {
    enable = true;
    domain = "pbx.artmann.tech"; # A/AAAA record must point here (domains repo)

    # Real certificate via Let's Encrypt; also provisions FreeSWITCH's
    # SIP-over-TLS listener (5061). Requires ports 80/443 reachable from the
    # internet. For a LAN-only host use the default self-signed mode instead.
    tls = {
      mode = "acme";
      acmeEmail = "lars@artmann.tech"; # CHANGEME if a role address is preferred
    };

    # Set when the host sits behind NAT (public IP to advertise in SIP/SDP).
    # Leave unset on a VPS that owns its public address.
    # natAddress = "203.0.113.10";

    # No plaintext secrets in the store: every credential comes from a
    # runtime file (exactly-one-of is asserted at eval time).
    eventSocketPasswordFile = "${secretsDir}/telephony_event_socket";
    turn.authSecretFile = "${secretsDir}/telephony_turn";

    extensions = {
      "1000" = {
        passwordFile = "${secretsDir}/telephony_ext_1000";
        displayName = "Alice";
      };
      "1001" = {
        passwordFile = "${secretsDir}/telephony_ext_1001";
        displayName = "Bob";
      };
    };

    ringGroups."2000" = {
      members = [
        "1000"
        "1001"
      ];
      timeoutSec = 25;
    };

    # CHANGEME: ITSP trunk. Uncomment and fill once you have a provider
    # account and DID (dialling PSTN answers 503 while this stays unset).
    # gateways.itsp = {
    #   proxy = "sip.provider.example";
    #   username = "acme-account";
    #   passwordFile = "${secretsDir}/telephony_gw_itsp";
    #   callerIdNumber = "441632960961";
    #   did = "441632960961";
    #   didDestination = "2000";
    #   # Defense in depth against SIP scanners: only the provider may hit
    #   # the external profile (SIP-layer ACL); pair with
    #   # firewall.restrictExternalTo (below) to also drop anyone else at the
    #   # firewall. List your provider's real source networks.
    #   # allowedCidrs = [ "203.0.113.0/24" ];
    # };

    # Firewall counterpart to gateway.allowedCidrs: restrict port 5080 to the
    # provider's networks at the firewall layer (uncomment with the gateway).
    # firewall.restrictExternalTo = [ "203.0.113.0/24" ];

    # Call detail records (one CSV row per leg) for billing/debugging.
    cdr.enable = true;

    # Recordings are personal data: keep consent law in mind (recording.enable
    # defaults to true; disable here if in doubt). Serving them over HTTPS is
    # opt-in and password-file-only by design:
    # recording.serve = {
    #   enable = true;
    #   basicAuthPasswordFile = "${secretsDir}/telephony_recordings";
    # };
  };

  # networking: DHCP on all interfaces by default; set a static address or
  # networkd links for a server whose IP must not move (the domain's DNS
  # record and the ITSP's access lists point at it).

  system.stateVersion = "26.05"; # set to the release you first install on
}
