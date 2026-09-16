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

## VM tests cannot catch initrd-driver gaps: they never boot the metal layout

tests/prod-boot.nix `mkForce`s the root to `/dev/vda` on QEMU's
virtio-blk bus (and neutralizes NIC/grub), so the real path — initrd
waiting for `/dev/disk/by-partlabel/disk-main-root` on Hetzner's
virtio-SCSI bus — is replaced wholesale by a stand-in that does not
need the drivers the real bus needs. A hand-written host with no
`hardware-configuration.nix` had zero virtio modules in
`boot.initrd.availableKernelModules`; first boot on real Hetzner
hardware hung forever at the root device wait while every VM suite was
green (2026-09-14, cost a full install cycle). Both hosts/pbx-prod and
the private flake now list `virtio_pci`/`virtio_blk`/`virtio_scsi`
explicitly, and `checks.initrd-audit` +
`nix run .#initrd-audit` (packages/initrd-audit) gate the initrd
drivers before any install hand-off. If a future test must prove
real-disk bootability, it has to boot the actual disko image through
the target bus (`virtualisation.diskInterface`), not an overridden
root device.

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
