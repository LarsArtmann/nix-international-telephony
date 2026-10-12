# The FreeSWITCH module set this stack builds — ONE home, two consumers:
#
#   * modules/telephony/pbx.nix passes it as freeswitch.override's
#     `modules` argument (that argument REPLACES nixpkgs' default set
#     wholesale — nixpkgs exposes no "default plus one" accessor), and
#   * tests/eval.nix resolves every entry against nixpkgs' module
#     universe, so an upstream rename or removal fails the cheap eval
#     check with a named message instead of a freeswitch build failure
#     one VM run in.
#
# Content: nixpkgs' v1.8.7-derived defaultModules list (see
# pkgs/by-name/fr/freeswitch/package.nix at the pinned rev) mirrored with
# exactly one addition — xml_int.curl (mod_xml_curl), the module the
# dynamic directory bridge (fs-directory.py) needs. A silently dropped
# entry still fails loudly at runtime: sofia missing = nothing registers
# (every VM test red), curl missing = telephony-webphone-dynamic-directory
# red.
{
  lib,
  stdenv,
  mods,
}:
with mods;
[
  applications.commands
  applications.conference
  applications.db
  applications.dptools
  applications.enum
  applications.esf
  applications.expr
  applications.fifo
  applications.fsv
  applications.hash
  applications.httapi
  applications.sms
  applications.spandsp
  applications.valet_parking
  applications.voicemail

  applications.curl

  codecs.amr
  codecs.b64
  codecs.g723_1
  codecs.g729
  codecs.h26x
  codecs.opus

  databases.mariadb
  databases.pgsql

  dialplans.asterisk
  dialplans.xml

  endpoints.loopback
  endpoints.rtc
  endpoints.skinny
  endpoints.sofia
  endpoints.verto

  event_handlers.cdr_csv
  event_handlers.cdr_sqlite
  event_handlers.event_socket

  formats.local_stream
  formats.native_file
  formats.png
  formats.sndfile
  formats.tone_stream

  languages.lua

  loggers.console
  loggers.logfile
  loggers.syslog

  say.en

  xml_int.cdr
  xml_int.rpc
  xml_int.scgi
  xml_int.curl
]
++ lib.optionals stdenv.hostPlatform.isLinux [ endpoints.gsmopen ]
