# Disk layout for the production host (Hetzner Cloud cx22 shape: single
# virtio-scsi disk as /dev/sda, legacy BIOS boot — Hetzner's x86 default).
# Imported only by nixosConfigurations.pbx-prod in flake.nix: nixos-anywhere
# runs disko against this definition before installing NixOS, and the disko
# module turns it into the runtime fileSystems. The boot-smoke test
# (tests/prod-boot.nix) does not import this file — the VM framework
# provides its own root device.
#
# If the server is ever switched to UEFI boot in the Hetzner console,
# replace this with an ESP partition + boot.loader.systemd-boot layout.
{
  disko.devices = {
    disk.main = {
      device = "/dev/sda";
      type = "disk";
      content = {
        type = "gpt";
        partitions = {
          # GRUB's BIOS-boot area on GPT (bare partition, no filesystem).
          boot = {
            size = "1M";
            type = "EF02";
            priority = 1;
          };
          root = {
            size = "100%";
            content = {
              type = "filesystem";
              format = "ext4";
              mountpoint = "/";
              mountOptions = [ "noatime" ];
            };
          };
        };
      };
    };
  };
}
