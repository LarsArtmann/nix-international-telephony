{
  fetchurl,
  lib,
  stdenv,
}:

let
  callie = fetchurl {
    url = "https://files.freeswitch.org/releases/sounds/freeswitch-sounds-en-us-callie-8000-1.0.52.tar.gz";
    hash = "sha256-++USlrpSgoZKjwJpqWjeB4O4iyp12tcQ7gdhODgqUVE=";
  };
  music = fetchurl {
    url = "https://files.freeswitch.org/releases/sounds/freeswitch-sounds-music-8000-1.0.52.tar.gz";
    hash = "sha256-JJHcuSppximwPqBw0kg5CKUuLFMN13eR9JpFpNcKqgc=";
  };
in
stdenv.mkDerivation {
  pname = "freeswitch-sounds";
  version = "1.0.52";

  sourceRoot = ".";
  buildCommand = ''
    mkdir -p $out/sounds
    tar -xzf ${callie} -C $out/sounds
    tar -xzf ${music} -C $out/sounds
  '';

  meta = {
    description = "FreeSWITCH sound prompts (en/us/callie) and music on hold, 8kHz";
    license = lib.licenses.mpl11;
    # The prompt pack (en/us/callie) is MPL-1.1 like FreeSWITCH itself.
    # The music-on-hold pack ships no license file; upstream documents it
    # as CC-BY — check attribution requirements before redistribution.
    platforms = [
      "x86_64-linux"
      "aarch64-linux"
    ];
  };
}
