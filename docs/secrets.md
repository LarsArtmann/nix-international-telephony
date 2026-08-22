# Managing telephony secrets with sops-nix

Every telephony credential has a `*File` twin so the secret never lands in
the world-readable Nix store:

| Plain option                       | File option                    |
| ---------------------------------- | ------------------------------ |
| `eventSocketPassword`              | `eventSocketPasswordFile`      |
| `extensions.<n>.password`          | `extensions.<n>.passwordFile`  |
| `gateways.<name>.password`         | `gateways.<name>.passwordFile` |
| `turn.authSecret`                  | `turn.authSecretFile`          |

`recording.serve.basicAuthPasswordFile` is file-only by design (serving
recordings without a runtime password file is refused by assertion).

Set exactly one of each pair — module assertions enforce this at eval time.
With a file set, the generated FreeSWITCH/coturn config carries a
`@TELEPHONY_*@` placeholder and the freeswitch unit's `ExecStartPre`
copies the config to a private runtime dir (`/var/lib/freeswitch/conf`,
mode 600) and splices the real value in from the file via systemd
`LoadCredential`. [`tests/secrets.nix`](../tests/secrets.nix) proves the
whole path in a VM: store purity, splice, digest REGISTERs, TURN
allocations, gateway REG state.

This document shows the sops-nix recipe; agenix works with the same file
layout. The recipe is deliberately **docs-only** — this repository does
not add sops-nix as a flake input or wire it into the example host; bring
your own secret manager and point the `*File` options at its outputs.

## 1. Host key

Generate an age key on the deployed host (or provision it however you
provision host state):

```console
mkdir -p /var/lib/sops-nix
nix shell nixpkgs#age-keygen -c sh -c 'age-keygen -o /var/lib/sops-nix/key.txt'
cat /var/lib/sops-nix/key.txt   # the "# public key:" line goes into .sops.yaml
```

`sops.age.generateKey = true` creates the key automatically on first
activation if you accept host-local keys.

## 2. `.sops.yaml` in your flake repo

```yaml
keys:
  - &pbx age1...your-host-public-key...
creation_rules:
  - path_regex: secrets/telephony\.yaml$
    key_groups:
      - age:
          - *pbx
```

## 3. Edit the secrets file

```console
nix shell nixpkgs#sops -c sops secrets/telephony.yaml
```

```yaml
telephony_event_socket: es-4d5e6f7g8h9i
telephony_ext_1000: a-real-sip-password
telephony_gw_itsp: provider-sip-secret
telephony_turn: turn-shared-secret
telephony_recordings: recordings-basic-auth-password
```

## 4. Wire sops-nix and the module

```nix
{
  inputs = {
    telephony.url = "github:LarsArtmann/nix-international-telephony";
    sops-nix = {
      url = "github:Mic92/sops-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { nixpkgs, telephony, sops-nix }: {
    nixosConfigurations.pbx = nixpkgs.lib.nixosSystem {
      system = "x86_64-linux";
      modules = [
        telephony.nixosModules.telephony
        sops-nix.nixosModules.sops
        {
          sops.defaultSopsFile = ./secrets/telephony.yaml;
          sops.age.keyFile = "/var/lib/sops-nix/key.txt";

          sops.secrets = {
            # Read once by PID1 for LoadCredential: root-only is fine.
            telephony_event_socket = { };
            telephony_ext_1000 = { };
            telephony_gw_itsp = { };
            telephony_recordings = { };
            # coturn's unit reads this file as the turnserver user in
            # preStart — hand it over explicitly. (sops renders parents
            # of /run/secrets root-owned and traversable, so only this
            # file needs adjusting.)
            telephony_turn = {
              owner = "turnserver";
              mode = "0440";
            };
          };

          services.telephony = {
            enable = true;
            domain = "pbx.example.com";

            eventSocketPasswordFile = "/run/secrets/telephony_event_socket";
            extensions."1000".passwordFile = "/run/secrets/telephony_ext_1000";
            gateways.itsp.passwordFile = "/run/secrets/telephony_gw_itsp";
            turn.authSecretFile = "/run/secrets/telephony_turn";
            recording.serve = {
              enable = true;
              basicAuthPasswordFile = "/run/secrets/telephony_recordings";
            };
            # … non-secret options as usual …
          };
        }
      ];
    };
  };
}
```

Defaults worth knowing (verified against the sops-nix module): secrets
render to `/run/secrets/<name>`, mode `0400`, owner/group `root`, loaded
from `sops.defaultSopsFile` unless overridden per secret.

## 5. Verify

```console
sudo -u turnserver cat /run/secrets/telephony_turn   # coturn can read its secret
sudo cat /run/secrets/telephony_event_socket         # … and the others exist
fs_cli -p "$(sudo cat /run/secrets/telephony_event_socket)" -x 'sofia status'
```

Store purity holds by construction: the only place the values can leak
into the store is a plain `password`-style option next to the file
variant — the module's exactly-one-of assertions reject that combination
at evaluation time.
