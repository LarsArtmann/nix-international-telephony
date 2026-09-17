# The operator window: a read-model HTTP API (api.py) plus the offline
# dialplan dry-run simulator (dialplan_sim.py), packaged with the static
# dashboard they serve (webroot/). Python stdlib only — there is no
# runtime dependency beyond the freeswitch package's fs_cli (PATH of the
# consuming systemd unit).
{
  lib,
  makeWrapper,
  python3,
  runCommand,
}:

runCommand "telephony-operator-0.1.0"
  {
    nativeBuildInputs = [ makeWrapper ];
    meta = {
      description = "Read-only operator window for the telephony stack (CDR viewer, live health, voicemail API, dialplan simulator)";
      license = lib.licenses.mit;
      platforms = lib.platforms.linux;
      mainProgram = "telephony-operator-api";
    };
  }
  ''
    mkdir -p $out/bin $out/share/telephony-operator/lib $out/share/telephony-operator/webroot
    install -m 0555 ${./api.py} $out/share/telephony-operator/lib/api.py
    install -m 0555 ${./dialplan_sim.py} $out/share/telephony-operator/lib/dialplan_sim.py
    install -m 0555 ${./webroot/index.html} $out/share/telephony-operator/webroot/index.html
    install -m 0555 ${./webroot/operator.css} $out/share/telephony-operator/webroot/operator.css
    install -m 0555 ${./webroot/operator.js} $out/share/telephony-operator/webroot/operator.js

    makeWrapper ${python3}/bin/python3 $out/bin/telephony-operator-api \
      --add-flags "$out/share/telephony-operator/lib/api.py"
    makeWrapper ${python3}/bin/python3 $out/bin/telephony-dialplan-simulate \
      --add-flags "$out/share/telephony-operator/lib/dialplan_sim.py"
  ''
