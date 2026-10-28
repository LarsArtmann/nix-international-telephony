# The native-OAuth recordings browser: a stdlib-only HTTP service that
# lists and streams recorded calls and owns its own OIDC login via the
# shared oidc_session helper (modules/telephony/oidc_session.py is
# installed alongside). No oauth2-proxy, no nginx auth_request — the
# owner directive (2026-10-28) is that apps do OAuth natively.
{
  lib,
  makeWrapper,
  python3,
  runCommand,
}:

runCommand "telephony-recordings-view-0.1.0"
  {
    nativeBuildInputs = [ makeWrapper ];
    meta = {
      description = "OIDC-native recordings browser for the telephony stack (directory listing + streaming, Pocket ID login)";
      license = lib.licenses.mit;
      platforms = lib.platforms.linux;
      mainProgram = "telephony-recordings-view";
    };
  }
  ''
    mkdir -p $out/bin $out/share/telephony-recordings-view/lib
    install -m 0555 ${./recordings_view.py} $out/share/telephony-recordings-view/lib/recordings_view.py
    install -m 0555 ${
      ../../modules/telephony/oidc_session.py
    } $out/share/telephony-recordings-view/lib/oidc_session.py

    makeWrapper ${python3}/bin/python3 $out/bin/telephony-recordings-view \
      --add-flags "$out/share/telephony-recordings-view/lib/recordings_view.py"
  ''
