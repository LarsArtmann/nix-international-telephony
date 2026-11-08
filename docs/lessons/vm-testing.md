# VM-testing lessons (long-form)

Moved verbatim from AGENTS.md 2026-09-16 to keep that file under its
line cap. AGENTS.md carries one-line pointers; the full stories live
here. Annotate, never rewrite — append new lessons at the bottom.

## FreeSWITCH never follows a BACKWARDS system-clock jump

Its internal clock is monotonic-plus-offset; a `date -s` into the past
is ignored indefinitely (probed live: 60s of `fs_cli -x 'strepoch'` /
`eval ${strftime(...)}` polling kept the pre-jump wall time), so
date-time dialplan conditions keep evaluating with the stale time and
time-window tests route the wrong leg — this made
`telephony-time-routing` fail deterministically on three independent
runs after its original "green". Restarting the unit re-reads the wall
clock, BUT CI runners saw the guest clock itself revert to host time
between `date -s` and the restart. Final design in
`tests/time-routing.nix`: one node per leg with a fixed QEMU RTC base
(`virtualisation.qemu.options = [ "-rtc base=<iso-time>" ]`) plus a
loud `date +%H` precondition assert — the guest boots at the wanted
time and nothing can drag it back.

## The metal boot path: proven in CI via kexec (was: impossible from a VM)

tests/prod-boot.nix `mkForce`s the root to `/dev/vda` on QEMU's
virtio-blk bus (and neutralizes NIC/grub), so the real path — initrd
waiting for `/dev/disk/by-partlabel/disk-main-root` on Hetzner's
virtio-SCSI bus — used to be untestable: a hand-written host with no
`hardware-configuration.nix` had zero virtio modules in
`boot.initrd.availableKernelModules`; first boot on real Hetzner
hardware hung forever at the root device wait while every VM suite was
green (2026-09-14, cost a full install cycle). Both hosts/pbx-prod and
the private flake now list `virtio_pci`/`virtio_blk`/`virtio_scsi`
explicitly; `checks.initrd-audit` +
`nix run .#initrd-audit` (packages/initrd-audit) gate the initrd
drivers before any install hand-off, and `checks.telephony-metal-boot`
(tests/metal-boot.nix) boots the path end to end:

- **`virtualisation.qemu.diskInterface = "scsi"` emulates an lsi53c895a
  HBA, NOT virtio-scsi** (sym53c8xx driver — proves the wrong driver
  entirely). Hetzner's bus is reproduced with
  `virtualisation.qemu.options = [ "-device virtio-scsi-pci,id=..."
  "-drive if=none,id=metal,file=empty0.qcow2,format=qcow2"
  "-device scsi-hd,bus=....0,drive=metal" ]` — declare the disk in
  `emptyDiskImages` (so the runner creates empty0.qcow2) but
  `lib.mkForce` `virtualisation.qemu.drives` down to the root drive only,
  or the framework also attaches it as virtio-blk (QEMU: drive in use).
- **The whole closure cannot be copied file-by-file through the virtiofs
  host-store mount**: virtiofsd runs with a 65536 fd hard limit
  (build-sandbox inherited; it warns at startup) and ~200k touched files
  exhaust it mid-copy — the guest sees cascading `Too many open files in
  system` from `cp`. Build ONE tarball of the closure outside the VM
  (`pkgs.closureInfo` + `tar -T store-paths`) and stream-extract it
  inside — a single sequential read.
- **kexec into the target toplevel** with the real bootspec cmdline
  (`init=<toplevel>/init` + `boot.kernelParams` + observability params
  `console=ttyS0,115200 loglevel=7 systemd.journald.forward_to_console=1`
  — kernel ext4/virtio messages stay under loglevel=4 otherwise). Assert
  with `machine.wait_for_console_text`: `Virtio SCSI HBA`,
  `EXT4-fs \(sda1\): mounted filesystem`, `Reached target (Local File
  Systems|Basic System)`.
- **After the jump there is no driver shell** (the new system's serial
  console is a getty). Trigger the jump from a transient unit so the
  driver shell returns its exit marker first
  (`machine.succeed("systemd-run --unit=... kexec -e")` — a bare
  `machine.execute("kexec -e")` kills the shell mid-command and the
  driver dies parsing its output), use ONLY console reads afterwards,
  and finish with `machine.crash()` (QEMU monitor, no guest shell) —
  the driver epilogue runs `machine.execute("sync")` on every machine
  where `is_up()` and crashes otherwise.
- The bootloader hop (GRUB on the EF02 partition) stays nixos-anywhere's
  tested path; the incident lived in initrd↔device, which kexec
  exercises with the verbatim artifacts.

## aarch64 CI on GitHub arm runners

`ubuntu-24.04-arm` is free for public repos but exposes NO /dev/kvm
(Azure arm VMs, no nested virt), so the job advertises
`system-features = nixos-test benchmark big-parallel` and builds a
KVM-feature-less test. The test driver's connect() retries the serial
shell only 10×30s (FIXED, not configurable from testScript) — full VM
suites never finish booting under TCG in that window; only the minimal
`telephony-boot-tcg` suite fits.

## The interactive test driver is the VM-state debugging superpower

`nix build .#checks.x86_64-linux.<suite>.driverInteractive --no-link
--print-out-paths`, write a probe script (plain `machine.succeed(...)`
calls), then `<path>/bin/nixos-test-driver --test-script /tmp/probe.py
--no-interactive`. Faster than a full suite rerun for "what does the
VM actually look like" questions.

Driver-drv discovery trap: `nix build ...driverInteractive` prints
the DRIVER drv path, not the runnable — the executable lives at
`<drv>/bin/nixos-test-driver`. And when several driverInteractive
builds exist, `ls -dt /nix/store/*driver*/bin/nixos-test-driver`
sorted by mtime lies across epoch-boundary rebuilds (store paths
re-hashed after an input bump shift the sort); prefer
`nix build --print-out-paths` output over `ls -dt` archaeology.

## Harness discipline: the round-10/26 CDR + dialplan harness postmortems

Ten VM runs (~90 min) burned on the CDR harness taught these the hard
way; they are the difference between a 3-run diagnosis and a
10-run rabbit hole:

- **Time-box harness rabbit holes at 3 runs; instrument before
  theorizing.** stderr to a file, full journal dumps — never
  `tail -40` your evidence: repeated trace greps on truncated tails
  produced confident wrong conclusions ("no authed INVITE") that the
  full log contradicted instantly.
- **A busy-spin loop that never `recv`s wedges the driver silently**
  (900 s kill, twice in one session): every parse pass must consume
  from the socket (`_parse_one` without `recv` spins forever).
- **`py_compile` green does not prove your edit landed** — a heredoc
  "rewrite" that silently failed still py_compiled the OLD file.
  After script surgery, grep for a NEW marker string you added.
- **`machine.execute` returns the DRIVER's exit status, not your
  curl's** — assert the `-w %{http_code}` OUTPUT, not the shell rc
  (one wasted VM build in the messaging suite).
- **Pipes mask exit codes: `cmd | tail` reports TAIL's rc** — the
  2026-11-08 check-vm timeout proof "passed" both arms because each
  probe ended in `| tail -3` and `$?` was tail's. The rule: run the
  probe with output redirected to a file (`> /tmp/x.log 2>&1;
  RC=$?`), then read the file — never pipe a verdict probe through
  anything. Same discipline inside testScripts: `machine.execute`
  returns (driver_rc, out) — assert the OUTPUT, or use
  `machine.succeed` which fails on non-zero rc itself.
- **vm-test-run store output is empty on SUCCESS** — building a NixOS
  test runs the test; an empty output path is the pass signal, and
  the receipts live in `nix log <drv>`. Read the FIRST build's log
  before re-building anything (the pbx-lens relock session rebuilt
  before reading and lost the evidence trail).
- **Keep diagnostic harnesses in-repo** (`scripts/nonce-deleter.py`,
  the custom-driver recipe above) — /tmp is where tooling goes to
  die; a later session had to RECONSTRUCT the nonce harness from a
  report because the original died in /tmp.
- **Concurrent VM-suite realization OOMs local full-check runs** (the
  2026-10-07 BuildFlow full-run triage era): heavy suites realize
  one-at-a-time locally or stay CI-only — the standing default is
  CI-only for the heavy pair, local realization only when triaging a
  specific red.
- **Parallel nix processes share the eval-cache sqlite and hit
  "database is locked/busy"** under BuildFlow's parallel nix steps —
  noise so far (every case logged "ignored"); if it ever corrupts,
  serialize the nix steps or shard the cache (the 2026-10-07 triage
  row keeps this open).

## VM tests that set the clock MUST stop NTP first

`systemctl stop systemd-timesyncd && timedatectl set-ntp false` before
`date -s` — otherwise timesyncd snaps the clock back mid-test and
time-window assertions flake mysteriously (cost a full suite run once).

## wait_for_freeswitch takes plain SECONDS

(tests/common.nix) and builds the `datetime.timedelta`s itself; call
sites passing `timedelta(...)` into it double-wrap and die at runtime
with `TypeError: unsupported type for timedelta seconds component`. The
test driver's own `wait_until_succeeds(timeout=...)` DOES take
timedeltas. A suite can green in CI while its kwargs-path is broken if
the kwargs are only used by a variant (TCG) that CI-x86 never ran.

## Scripted-networking interface configs wedge VM tests on absent devices

A host template's `networking.interfaces.ens3` (Hetzner static IPv6)
generates `network-addresses-ens3.service`, which systemd parks behind
`sys-subsystem-net-devices-ens3.device`; `network-online.target` wants
that unit, and everything ordered after network-online (freeswitch,
coturn) hangs forever with an EMPTY journal (300s test timeout,
`Job: NNN` pending in status). `systemctl list-jobs --all` via the
interactive driver is the decisive probe. tests/prod-boot.nix
neutralizes the template's NIC config the same way it neutralizes
fileSystems/grub (mkForce {} + defaultGateway6 null + unit
enable=false). A prior session's "green" prod-boot run is unexplained
against this deterministic wedge — re-verify old green claims before
building on them.

## Eval-only regression checks (tests/eval.nix → checks.telephony-eval)

Force `system.build.toplevel.drvPath` for all three `tls.mode` variants
(needs boot fixtures: `fileSystems`/`grub`/`stateVersion` in
`tests/tls-mode-host.nix`, else NixOS's own assertions fail) and grep
the generated directory XML for the dial-string's single-dollar runtime
vars. First run caught a real bug: `tls.mode = "acme"` had a
hand-rolled `security.acme.certs` entry with NO challenge provider —
security.acme's assertion kills the full eval. Correct wiring: delegate
to the nginx vhost's `enableACME` (challenge location, group, reloads
included).

## Never hash a path flake inside the shared-store test VM

The test framework shares the host store via virtiofsd with fd
passthrough (a bounded pool, ~64k). Any nix command that LOCKS a path
input — `nix flake metadata nixpkgs`, `nix eval nixpkgs#lib.version`,
`nix run nixpkgs#…` — computes the input's narHash and therefore walks
the entire nixpkgs tree (100k+ files) through that fd pool, which
exhausts it: `virtiofsd ... No more file descriptors available to the
guest` → `Too many open files in system`. Harmless on a real host's
local disk; fatal in every VM suite. Consequence for tests asserting
the ops tooling's pinned registry (tests/pbx.nix): prove the chain
piecewise instead — `nix registry list` (proves flakes CLI active, no
global entries, the `system flake:nixpkgs path:/nix/store/...` pin)
plus `test -f <path>/flake.nix` (proves the source is in the guest
closure, so offline resolution works).

## Sweep node-level `imports` when removing a module option/default

Fixtures import the module under test at NODE granularity
(`modules = [ ../modules/telephony ]` inside a `nodes.<name> = { … }`
block), not only at file level in a shared fixture. A sweep that greps
only top-level files for consumers of an option default misses the node
blocks — removing the default then breaks an unrelated suite's eval one
full VM-gate cycle later (~25 min). Sweep `imports = [...]` inside
`nodes.*` too (the 2026-09-18 webphone-extraction miss:
`tests/prod-boot.nix`'s NODE imported `../modules/telephony` and lost
the `webphone.package` default).

## The test driver TYPE-CHECKS the script; `systemctl show --value` is not a path source

Two traps from the passkey lane (2026-10-05, each cost a full VM run):

- The driver runs a static type check on the generated script
  (`testScriptWithTypes`, disable via `skipTypeCheck`). Bare
  `re.search(...).group(1)` fails with
  `` Attribute `group` is not defined on `None` `` — bind the match and
  `assert m is not None` first (the /metrics block in
  `tests/webphone.nix` was already the house pattern; follow it).
- `systemctl show -p ExecStart --value webphone` prints a
  `{ path=…; argv[]={…}; }` STRUCT on current systemd, not a bare path
  — a "path" extracted from it starts with `{` and quietly poisons
  downstream commands (the assertion message then looks like a dict
  dump). Read the RUNNING binary from
  `readlink /proc/$(systemctl show -p MainPID --value <unit>)/exe`
  instead; the same /proc environ read the suites already use is the
  pattern for env vars (`WEBPHONE_CONFIG`).
