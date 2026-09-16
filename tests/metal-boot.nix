# Metal-path boot proof: the 2026-09-14 first install hung forever in the
# initrd waiting for /dev/disk/by-partlabel/disk-main-root on Hetzner's
# virtio-scsi bus, while every VM suite stayed green (tests/prod-boot.nix
# boots a mkForce'd /dev/vda stand-in on QEMU's virtio-blk bus; the
# framework's `diskInterface = "scsi"` is an lsi53c895a HBA, NOT the
# virtio-scsi Hetzner actually has).
#
# What this suite proves, end to end with the REAL pbx-prod artifacts:
#   1. a GPT partition named disk-main-root behind a virtio-scsi-pci HBA
#      is enumerable by the pbx-prod initrd (virtio_pci/virtio_scsi load),
#   2. the initrd's embedded fstab (root=fstab, the exact prod boot
#      cmdline from bootspec) mounts it instead of hanging at the root
#      device wait — the precise Hetzner failure mode,
#   3. stage 2 (systemd) starts from that root — switch_root succeeded.
#
# Mechanism: the base VM (virtio-blk root, host store mounted) partitions a
# second disk attached to `-device virtio-scsi-pci`, copies the pbx-prod
# closure onto it (what nixos-anywhere's nixos-install leaves behind), then
# kexec's into the pbx-prod kernel+initrd with the prod kernel params. The
# bootloader hop (GRUB on the EF02 partition) is skipped deliberately:
# grub-install is nixos-anywhere's tested path, and the incident lived in
# initrd↔device, which kexec exercises verbatim.
#
# The only cmdline additions are observability params (console, loglevel,
# journal forward-to-console) — they change no boot decision.
{
  prod,
}:
let
  # console/loglevel/journald-forwarding appended for serial assertions.
  cmdline = "init=${prod.toplevel}/init ${prod.params} console=ttyS0,115200 loglevel=7 systemd.journald.forward_to_console=1";
in
{
  name = "telephony-metal-boot";

  nodes.machine =
    {
      lib,
      pkgs,
      ...
    }:
    {
      # Closure copy (1.4 GiB) through page cache: give the VM headroom.
      virtualisation.memorySize = 4096;
      # The metal disk: created by the framework in the VM runner's tmpdir
      # (empty0.qcow2) but NOT auto-attached — see the drives override below.
      virtualisation.emptyDiskImages = [ 8192 ];
      # Replace the framework's drive list so empty0.qcow2 is not attached
      # as virtio-blk; only the root drive stays (verbatim framework shape).
      virtualisation.qemu.drives = lib.mkForce [
        {
          name = "root";
          file = ''"$NIX_DISK_IMAGE"'';
          driveExtraOpts.cache = "writeback";
          driveExtraOpts.werror = "report";
          deviceExtraOpts.bootindex = "1";
          deviceExtraOpts.serial = "root";
        }
      ];
      # Attach the metal disk the way Hetzner does: a virtio-scsi HBA.
      # (diskInterface = "scsi" would emulate lsi53c895a instead.)
      virtualisation.qemu.options = [
        "-device virtio-scsi-pci,id=hetzner"
        "-drive if=none,id=metal,file=empty0.qcow2,format=qcow2"
        "-device scsi-hd,bus=hetzner.0,drive=metal"
      ];
      # The pbx-prod closure lands in the VM's store (registered via the
      # framework's regInfo), readable through the host store mount.
      virtualisation.additionalPaths = [ prod.toplevel ];

      environment.systemPackages = with pkgs; [
        gptfdisk # sgdisk: create the GPT partition label disko names
        e2fsprogs # mkfs.ext4
        kexec-tools
      ];
    };

  testScript = ''
    import datetime

    machine.wait_for_unit("multi-user.target")

    with machine.nested("metal disk sits behind the virtio-scsi HBA"):
        sysfs = machine.succeed("readlink -f /sys/block/sda").strip()
        assert "virtio" in sysfs, sysfs

    with machine.nested("carve the disko layout: GPT partition disk-main-root"):
        machine.succeed("sgdisk -o -n 1:0:0 -t 1:8300 -c 1:disk-main-root /dev/sda")
        machine.wait_for_path("/dev/disk/by-partlabel/disk-main-root")
        machine.succeed("mkfs.ext4 -q /dev/disk/by-partlabel/disk-main-root")

    with machine.nested("populate the root with the pbx-prod closure"):
        machine.succeed("mount /dev/disk/by-partlabel/disk-main-root /mnt")
        machine.succeed(
            "mkdir -p /mnt/nix/store /mnt/nix/var/nix/profiles"
            " /mnt/etc /mnt/var /mnt/run /mnt/root /mnt/home /mnt/tmp"
        )
        machine.succeed("chmod 1777 /mnt/tmp")
        machine.succeed(
            "nix-store -qR ${prod.toplevel}"
            " | xargs -d '\\n' cp -an --parents -t /mnt"
        )
        machine.succeed("ln -sfn ${prod.toplevel} /mnt/nix/var/nix/profiles/system")

    with machine.nested("kexec into the real pbx-prod kernel + initrd"):
        cmdline = "${cmdline}"
        machine.succeed(
            f"kexec -l ${prod.kernel}"
            f" --initrd=${prod.initrd}"
            f" --command-line='{cmdline}'"
        )
        # execute (not succeed): the shell dies with the old system.
        machine.execute("kexec -e")

    # --- The Hetzner incident, replayed: if the initrd lacked virtio_scsi
    # --- or could not resolve the by-partlabel root, boot would hang at
    # --- the root wait and none of these markers would ever appear.
    with machine.nested("prod initrd binds the virtio-scsi HBA"):
        machine.wait_for_console_text(
            r"Virtio SCSI HBA", timeout=datetime.timedelta(minutes=2)
        )

    with machine.nested("prod initrd mounts the by-partlabel root"):
        machine.wait_for_console_text(
            r"EXT4-fs \(sda1\): mounted filesystem",
            timeout=datetime.timedelta(minutes=2),
        )

    with machine.nested("stage 2 systemd starts from the metal root"):
        machine.wait_for_console_text(
            r"Reached target (Local File Systems|Basic System)",
            timeout=datetime.timedelta(minutes=3),
        )

    # If we got here the boot path works; capture the tail for the log.
    machine.sleep(5)
    print(machine.get_console_log()[-4000:])
  '';
}
