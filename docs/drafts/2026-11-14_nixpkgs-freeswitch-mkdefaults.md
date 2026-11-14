# Draft: nixpkgs services.freeswitch — mkDefault the ExecStart/CPUSchedulingPolicy plain defs

Status: DRAFT (file-ready), owner to submit. Prepared 2026-11-14 during
the SUPERB backlog execution (M30); verified at our pinned nixpkgs
`d4f25a3e562008648d45bcf2d70bcc7422cad84e`,
`nixos/modules/services/misc/freeswitch.nix` (the file moved from
`services/networking/` to `services/misc/` — cite the new path).

## Verified evidence (this repo, 2026-11-14)

Both values are PLAIN definitions in `systemd.services.freeswitch
.serviceConfig`:

- `ExecStart = "${pkg}/bin/freeswitch -nf --conf ... --log ... --db ..."`
  (~line 90) — a consumer that needs to adjust ONE flag (e.g. drop
  `-nf`, add `-nonat`, or point at a runtime-rendered config tree)
  cannot override without `mkForce`, which then silently DIVERGES from
  every upstream improvement to the flags (the exact drift this
  consumer carries today: nix-international-telephony
  `modules/telephony/pbx.nix` forces a full ExecStart mirror).
- `CPUSchedulingPolicy = "fifo";` (line 97) — opinionated for a plain
  module: real-time scheduling requires appropriate limits/capabilities
  to be meaningful, and a consumer running FreeSWITCH under different
  host-level scheduling policy (e.g. alongside an RT-budgeted audio
  pipeline) must mkForce it away.

`configDir` (line 48) already exists as an option — the earlier ask for
a config-dir knob is OBSOLETE; only the two plain defs above remain.

## Proposed change (minimal, behavior-preserving)

```diff
-        ExecStart = "${pkg}/bin/freeswitch -nf ...
+        ExecStart = lib.mkDefault "${pkg}/bin/freeswitch -nf ...
-        CPUSchedulingPolicy = "fifo";
+        CPUSchedulingPolicy = lib.mkDefault "fifo";
```

`mkDefault` keeps every current deployment byte-identical (no consumer
sets these today without already forcing them) while letting module
consumers override with plain assignments. An alternative shape: hoist
the flags into an `extraOptions`-style list option — larger surface, not
required for the fix.

## Consumer impact statement

nix-international-telephony (public NixOS telephony stack,
github.com/LarsArtmann/nix-international-telephony) currently mirrors
the ExecStart with mkForce to add runtime-rendered config paths and
drops the fifo policy for host-level control; with mkDefaults upstream,
both forces retire and the mirror-drift class dies.
