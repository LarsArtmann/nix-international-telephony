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

    # NixOS initrds are cpio archives, optionally compressed (zstd default;
    # gzip/xz/lz4 fallbacks) and optionally PREFIXED with an uncompressed
    # microcode cpio (early-microcode) — the kernel walks all concatenated
    # segments, so the audit must too. Walk segment by segment: probe each
    # 512-byte block for a known magic, list plain-cpio segments up to their
    # TRAILER!!! (cpio reports the consumed blocks on stderr; a 4 KiB pad may
    # follow before the next magic), then hand the compressed tail to the
    # matching decompressor. Every segment is staged to a temp file first:
    # cpio exits at the trailer WITHOUT draining stdin, so under pipefail a
    # piped producer would die of SIGPIPE and false-reject a good archive.
    tmpdir="$(mktemp -d)"
    trap 'rm -rf "$tmpdir"' EXIT
    seg="$tmpdir/segment"
    listing="$tmpdir/listing"
    cpio_err="$tmpdir/cpio-err"
    : > "$listing"

    probe() {
      # classify the segment magic at 512-byte block $1 ("" when unknown)
      hex="$(dd if="$initrd" bs=512 skip="$1" count=1 status=none 2>/dev/null | od -A n -t x1 -N 6 | tr -d ' \n')"
      case "$hex" in
        303730373031*|303730373032*) echo cpio ;;
        28b52ffd*) echo zstd ;;
        1f8b*) echo gzip ;;
        fd377a585a00*) echo xz ;;
        02214c18*|04224d18*) echo lz4 ;;
        *) echo "" ;;
      esac
    }

    total_blocks=$(( ($(stat -c%s "$initrd") + 511) / 512 ))
    skip=0
    while [ "$skip" -lt "$total_blocks" ]; do
      kind="$(probe "$skip")"
      case "$kind" in
        cpio)
          dd if="$initrd" of="$seg" bs=512 skip="$skip" status=none
          if ! cpio -t < "$seg" >> "$listing" 2>"$cpio_err"; then
            echo "initrd-audit: cpio failed on the plain segment at block $skip of '$initrd'" >&2
            exit 1
          fi
          used="$(sed -n 's/^\([0-9][0-9]*\) blocks$/\1/p' "$cpio_err" | tail -n1)"
          if [ -z "$used" ] || [ "$used" -eq 0 ]; then
            echo "initrd-audit: cpio consumed no blocks for the segment at $skip of '$initrd'" >&2
            exit 1
          fi
          skip=$((skip + used))
          # the plain segment may be zero-padded up to the next 4 KiB
          # boundary (early-microcode) — scan one pad page for the next magic
          next=""
          for pad in 0 1 2 3 4 5 6 7; do
            cand=$((skip + pad))
            [ "$cand" -lt "$total_blocks" ] || break
            if [ -n "$(probe "$cand")" ]; then
              skip=$cand
              next=1
              break
            fi
          done
          # no further magic within the pad window: only trailing zeros remain
          [ -n "$next" ] || skip=$total_blocks
          ;;
        zstd|gzip|xz|lz4)
          dd if="$initrd" of="$seg" bs=512 skip="$skip" status=none
          # a decompressor that cannot finish the stream still leaves cpio's
          # appended listing intact; a fully unusable segment appends nothing
          # and the empty-listing check below rejects it
          case "$kind" in
            zstd) zstdcat "$seg" 2>/dev/null | cpio -t >> "$listing" 2>/dev/null || true ;;
            gzip) gzip -dc "$seg" 2>/dev/null | cpio -t >> "$listing" 2>/dev/null || true ;;
            xz) xzcat "$seg" 2>/dev/null | cpio -t >> "$listing" 2>/dev/null || true ;;
            lz4) lz4cat "$seg" 2>/dev/null | cpio -t >> "$listing" 2>/dev/null || true ;;
          esac
          # the compressed segment is the tail by construction
          skip=$total_blocks
          ;;
        *)
          echo "initrd-audit: unrecognized segment magic at block $skip of '$initrd' (zstd/gzip/xz/lz4/cpio expected)" >&2
          exit 1
          ;;
      esac
    done

    if [ ! -s "$listing" ]; then
      echo "initrd-audit: could not parse '$initrd' as cpio segment(s) (any of zstd/gzip/xz/lz4/plain)" >&2
      echo "initrd-audit: inspect manually: zstdcat $initrd | cpio -t | less" >&2
      exit 1
    fi

    missing=""
    present=""
    IFS=','
    for module in $modules; do
      # greps the staged listing file directly — no pipe, no writer SIGPIPE
      if grep -E "(^|/)$module\.ko(\.[a-z0-9]+)?$" "$listing" >/dev/null; then
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
