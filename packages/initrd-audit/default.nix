{
  writeShellApplication,
  cpio,
  zstd,
  gzip,
  xz,
  lz4,
}:

writeShellApplication {
  name = "initrd-audit";

  runtimeInputs = [
    cpio
    zstd
    gzip
    xz
    lz4
  ];

  text = ''
    # Gate before any install hand-off: prove the built initrd carries the
    # target platform's storage bus drivers. The 2026-09-14 first boot on
    # Hetzner hung forever at the root-device wait because the initrd had
    # zero virtio drivers — while eval, build, and every VM suite were
    # green (the VM test boots a mkForce'd stand-in root on virtio-blk).
    set -euo pipefail

    platform="cloud"
    path=""

    usage() {
      cat <<EOF
    Usage: initrd-audit [--platform cloud|metal] <toplevel-dir | initrd-file>
      --platform cloud  require virtio_pci, virtio_blk, virtio_scsi (QEMU/Hetzner Cloud)
      --platform metal  require nvme, ahci (bare NVMe/SATA disks)
      --modules a,b,c   explicit module list, overrides --platform
      <path>            a NixOS toplevel directory (uses <path>/initrd)
                        or the initrd file itself
    EOF
      exit 2
    }

    modules=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --platform)
          [ $# -ge 2 ] || usage
          platform="$2"
          shift 2
          ;;
        --modules)
          [ $# -ge 2 ] || usage
          modules="$2"
          shift 2
          ;;
        -h|--help) usage ;;
        -*)
          echo "initrd-audit: unknown option: $1" >&2
          usage
          ;;
        *)
          if [ -n "$path" ]; then
            echo "initrd-audit: unexpected extra argument: $1" >&2
            usage
          fi
          path="$1"
          shift
          ;;
      esac
    done
    [ -n "$path" ] || usage

    case "$platform" in
      cloud) [ -n "$modules" ] || modules="virtio_pci,virtio_blk,virtio_scsi" ;;
      metal) [ -n "$modules" ] || modules="nvme,ahci" ;;
      *)
        echo "initrd-audit: unknown platform '$platform' (cloud|metal)" >&2
        exit 2
        ;;
    esac

    if [ -d "$path" ]; then
      initrd="$path/initrd"
    else
      initrd="$path"
    fi
    if [ ! -f "$initrd" ]; then
      echo "initrd-audit: no initrd at '$initrd' (pass a toplevel dir or initrd file)" >&2
      exit 2
    fi

    # Initrds here are zstd cpio archives (gzip/xz/lz4/plain kept as
    # fallbacks). A decompressor that cannot parse the stream makes cpio
    # fail, so the first cascade arm that lists cleanly wins.
    listing=""
    for decompress in \
      "zstdcat" \
      "gzip -dc" \
      "xzcat" \
      "lz4cat" \
      "cat"
    do
      if listing=$($decompress "$initrd" 2>/dev/null | cpio -t 2>/dev/null); then
        break
      fi
      listing=""
    done
    if [ -z "$listing" ]; then
      echo "initrd-audit: could not parse '$initrd' as a cpio archive (any of zstd/gzip/xz/lz4/plain)" >&2
      echo "initrd-audit: inspect manually: zstdcat $initrd | cpio -t | less" >&2
      exit 1
    fi

    missing=""
    present=""
    IFS=','
    for module in $modules; do
      if printf '%s\n' "$listing" | grep -Eq "(^|/)$module\.ko(\.[a-z0-9]+)?$"; then
        present="$present $module"
      else
        missing="$missing $module"
      fi
    done
    unset IFS

    echo "initrd:     $initrd"
    echo "platform:   $platform"
    echo "present:   $present"
    if [ -n "$missing" ]; then
      echo "MISSING:  $missing" >&2
      echo "initrd-audit: FAIL — the initrd cannot reach the root disk on this platform;" >&2
      echo "add the missing modules to boot.initrd.availableKernelModules and rebuild." >&2
      exit 1
    fi
    echo "initrd-audit: OK"
  '';

  meta.description = "Assert a built initrd contains the target platform's storage bus drivers";
}
