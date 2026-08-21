# Pure generator: turns telephony settings into a FreeSWITCH `configDir` overlay
# for the upstream `services.freeswitch` NixOS module
# (see nixpkgs nixos/modules/services/misc/freeswitch.nix).
#
# The overlay replaces the handful of vanilla-template files that define the
# PBX behaviour; every other file from the package's vanilla template
# (voicemail, conference, lang prompts, ...) stays as-is.
{
  lib,
  pkgs,
}:

{
  # SIP domain; also the realm phones register against.
  domain,
  # FreeSWITCH sound prompt package (packages/sounds.nix) or null to disable
  # prompts/music (voicemail becomes unusable without prompts).
  soundsDir ? null,
  # Attrs keyed by extension number:
  #   <number> = { password, displayName, allowInternational, vmPassword }
  extensions,
  # Attrs keyed by ring-group number:
  #   <number> = { members = [ "1000" ... ]; timeoutSec; voicemailMember; }
  ringGroups ? { },
  # null, or: { name, proxy, realm, username, password, register,
  #             allowedCidrs, callerIdNumber, did, didDestination,
  #             dialPrefix, fromUser, fromDomain }
  gateway ? null,
  # Event socket (fs_cli) password. Listens on 127.0.0.1 only.
  eventSocketPassword,
  recordingsDir ? "/var/lib/freeswitch/recordings",
  enableRecording ? true,
  cdrLogBase ? "/var/lib/freeswitch",
  enableCdr ? false,
  rtpStartPort ? 16384,
  rtpEndPort ? 16584,
  # Public IP when the PBX sits behind NAT (advertised in SDP/Via).
  natAddress ? null,
  # Plain-WS SIP transport consumed by the nginx TLS proxy.
  wsBindAddress ? "127.0.0.1",
  wsBindPort ? 5066,
  # Certificate directory for SIP-over-TLS when the operator provisions one
  # (e.g. from ACME); sofia reads agent.pem (cert+key) and cafile.pem from
  # here. null = FreeSWITCH self-generates its usual certificates.
  tlsCertDir ? null,
}:

let
  inherit (lib) concatStrings escapeXML optionalString;

  externalIp = if natAddress != null then natAddress else "$\${local_ip_v4}";
  soundPrefix = optionalString (soundsDir != null) "${soundsDir}/en/us/callie";
  holdMusic =
    if soundsDir != null then "local_stream://moh" else "tone_stream://%(2000,4000,440,480)";

  recordingActions =
    destination:
    optionalString enableRecording ''
      <action application="set" data="RECORD_STEREO=true"/>
      <action application="set" data="media_bug_answer_req=true"/>
      <action application="record_session" data="${recordingsDir}/''${uuid}_${destination}.wav"/>
    '';

  userXml = number: user: ''
    <user id="${number}">
      <params>
        <param name="password" value="${escapeXML user.password}"/>
        <param name="vm-password" value="${escapeXML user.vmPassword}"/>
      </params>
      <variables>
        <variable name="toll_allow" value="${
          if user.allowInternational then "domestic,international,local" else "domestic,local"
        }"/>
        <variable name="accountcode" value="${number}"/>
        <variable name="user_context" value="default"/>
        <variable name="effective_caller_id_name" value="${escapeXML user.displayName}"/>
        <variable name="effective_caller_id_number" value="${number}"/>
        ${optionalString (gateway != null) ''
          <variable name="outbound_caller_id_name" value="${escapeXML gateway.callerIdNumber}"/>
          <variable name="outbound_caller_id_number" value="${escapeXML gateway.callerIdNumber}"/>
        ''}
      </variables>
    </user>
  '';

  extensionDialplanEntry = number: _: ''
    <extension name="extension_${number}">
      <condition field="destination_number" expression="^${number}$">
        <action application="set" data="hangup_after_bridge=true"/>
        <action application="set" data="continue_on_fail=true"/>
        <action application="set" data="originate_timeout=30"/>
        ${recordingActions number}
        <action application="bridge" data="user/${number}"/>
        <action application="answer"/>
        <action application="sleep" data="1000"/>
        <action application="voicemail" data="default ''$''${domain} ${number}"/>
      </condition>
    </extension>
  '';

  ringGroupEntry = number: group: ''
    <extension name="ring_group_${number}">
      <condition field="destination_number" expression="^${number}$">
        <action application="set" data="ringback=''$''${us-ring}"/>
        <action application="set" data="hangup_after_bridge=true"/>
        <action application="set" data="continue_on_fail=true"/>
        <action application="set" data="originate_timeout=${toString group.timeoutSec}"/>
        ${recordingActions number}
        <action application="bridge" data="${
          lib.concatStringsSep "," (map (m: "user/${m}") group.members)
        }"/>
        <action application="answer"/>
        <action application="sleep" data="1000"/>
        <action application="voicemail" data="default ''$''${domain} ${group.voicemailMember}"/>
      </condition>
    </extension>
  '';

  gatewayXml = optionalString (gateway != null) ''
    <gateway name="${escapeXML gateway.name}">
      <param name="username" value="${escapeXML gateway.username}"/>
      <param name="password" value="${escapeXML gateway.password}"/>
      <param name="proxy" value="${escapeXML gateway.proxy}"/>
      <param name="realm" value="${escapeXML gateway.realm}"/>
      <param name="register" value="${lib.boolToString gateway.register}"/>
      ${optionalString (gateway.fromUser != null) ''
        <param name="from-user" value="${escapeXML gateway.fromUser}"/>
        <param name="from-domain" value="${escapeXML gateway.fromDomain}"/>
      ''}
    </gateway>
  '';

  # Name of the inbound ACL on the external profile when the operator
  # listed the provider's source addresses.
  inboundAclName = "trusted-itsp";

  # ACL nodes for gateway.allowedCidrs; omitted entirely when unconfigured
  # (the package's vanilla acl.conf.xml stays in place then).
  gatewayAllowedCidrs = if gateway == null then [ ] else gateway.allowedCidrs;

  pstnEntry =
    if gateway != null then
      ''
        <extension name="pstn_international">
          <condition field="''${toll_allow}" expression="international"/>
          <condition field="destination_number" expression="^\+?([1-9]\d{7,14})$">
            <action application="set" data="effective_caller_id_number=${escapeXML gateway.callerIdNumber}"/>
            <action application="set" data="effective_caller_id_name=${escapeXML gateway.callerIdNumber}"/>
            ${recordingActions "pstn"}
            <action application="bridge" data="sofia/gateway/${escapeXML gateway.name}/${escapeXML gateway.dialPrefix}$1"/>
          </condition>
        </extension>
        <extension name="pstn_denied">
          <condition field="destination_number" expression="^\+?\d{8,15}$">
            <action application="hangup" data="call_rejected"/>
          </condition>
        </extension>
      ''
    else
      ''
        <extension name="pstn_no_gateway">
          <condition field="destination_number" expression="^\+?\d{8,15}$">
            <action application="hangup" data="normal_temporary_failure"/>
          </condition>
        </extension>
      '';

  # Inbound ACL file, emitted into the config set only when the operator
  # listed CIDRs (see the optionalAttrs merge at the attrset root); without
  # it the package's vanilla acl.conf.xml stays in place and nothing
  # references the trusted-itsp list.
  aclConfXml = pkgs.writeText "acl.conf.xml" ''
    <configuration name="acl.conf" description="Network Lists">
      <network-lists>
        <list name="${inboundAclName}" default="deny">
          ${concatStrings (
            map (cidr: ''
              <node type="allow" cidr="${escapeXML cidr}"/>
            '') gatewayAllowedCidrs
          )}
        </list>
      </network-lists>
    </configuration>
  '';

  # CSV call detail records, only when the operator enables them; without
  # this file the package's vanilla cdr_csv.conf.xml stays in place.
  cdrCsvConfXml = pkgs.writeText "cdr_csv.conf.xml" ''
    <configuration name="cdr_csv.conf" description="CDR CSV Format">
      <settings>
        <!-- mod_cdr_csv always appends "cdr-csv" to log-base. -->
        <param name="log-base" value="${cdrLogBase}"/>
        <param name="default-template" value="example"/>
        <param name="legs" value="a"/>
        <param name="rotate-on-hup" value="false"/>
      </settings>
    </configuration>
  '';

in
(lib.optionalAttrs (gatewayAllowedCidrs != [ ]) {
  "autoload_configs/acl.conf.xml" = aclConfXml;
})
// (lib.optionalAttrs enableCdr {
  "autoload_configs/cdr_csv.conf.xml" = cdrCsvConfXml;
})
// {
  "vars.xml" = pkgs.writeText "vars.xml" ''
    <include>
      <!-- Placeholder: every user in directory/default.xml carries its own password. -->
      <X-PRE-PROCESS cmd="set" data="default_password=disabled-by-nix-telephony"/>
      <X-PRE-PROCESS cmd="set" data="domain=${escapeXML domain}"/>
      <X-PRE-PROCESS cmd="set" data="domain_name=''$''${domain}"/>
      <X-PRE-PROCESS cmd="set" data="hold_music=${holdMusic}"/>
      ${optionalString (soundsDir != null) ''
        <X-PRE-PROCESS cmd="set" data="sound_prefix=${soundPrefix}"/>
      ''}
      <X-PRE-PROCESS cmd="set" data="global_codec_prefs=OPUS,G722,PCMU,PCMA"/>
      <X-PRE-PROCESS cmd="set" data="outbound_codec_prefs=PCMU,PCMA,G722,OPUS"/>
      <X-PRE-PROCESS cmd="set" data="internal_sip_port=5060"/>
      <X-PRE-PROCESS cmd="set" data="internal_tls_port=5061"/>
      <X-PRE-PROCESS cmd="set" data="external_sip_port=5080"/>
      <X-PRE-PROCESS cmd="set" data="internal_ssl_enable=true"/>
      <X-PRE-PROCESS cmd="set" data="internal_auth_calls=true"/>
      <X-PRE-PROCESS cmd="set" data="sip_tls_version=tlsv1.2"/>
      <X-PRE-PROCESS cmd="set" data="us-ring=%(2000, 4000, 440, 480)"/>
      <X-PRE-PROCESS cmd="set" data="recordings_dir=${recordingsDir}"/>
      <X-PRE-PROCESS cmd="set" data="external_rtp_ip=${externalIp}"/>
      <X-PRE-PROCESS cmd="set" data="external_sip_ip=${externalIp}"/>
    </include>
  '';

  "autoload_configs/modules.conf.xml" = pkgs.writeText "modules.conf.xml" ''
    <configuration name="modules.conf" description="Modules">
      <modules>
        <!-- Loggers -->
        <load module="mod_console"/>
        <load module="mod_logfile"/>
        <!-- Event handlers -->
        <load module="mod_event_socket"/>
        <load module="mod_cdr_csv"/>
        <!-- Endpoints -->
        <load module="mod_sofia"/>
        <load module="mod_loopback"/>
        <!-- Applications -->
        <load module="mod_commands"/>
        <load module="mod_conference"/>
        <load module="mod_dptools"/>
        <load module="mod_expr"/>
        <load module="mod_voicemail"/>
        <!-- Dialplan -->
        <load module="mod_dialplan_xml"/>
        <!-- Codecs -->
        <load module="mod_opus"/>
        <!-- Formats -->
        <load module="mod_sndfile"/>
        <load module="mod_native_file"/>
        <load module="mod_tone_stream"/>
        <load module="mod_local_stream"/>
        <!-- Say -->
        <load module="mod_say_en"/>
      </modules>
    </configuration>
  '';

  "autoload_configs/event_socket.conf.xml" = pkgs.writeText "event_socket.conf.xml" ''
    <configuration name="event_socket.conf" description="Socket Client">
      <settings>
        <param name="nat-map" value="false"/>
        <param name="listen-ip" value="127.0.0.1"/>
        <param name="listen-port" value="8021"/>
        <param name="password" value="${escapeXML eventSocketPassword}"/>
      </settings>
    </configuration>
  '';

  "autoload_configs/switch.conf.xml" = pkgs.writeText "switch.conf.xml" ''
    <configuration name="switch.conf" description="Core Configuration">
      <settings>
        <param name="colorize-console" value="true"/>
        <param name="max-db-handles" value="50"/>
        <param name="db-handle-timeout" value="10"/>
        <param name="max-sessions" value="1000"/>
        <param name="sessions-per-second" value="30"/>
        <param name="loglevel" value="info"/>
        <param name="rtp-start-port" value="${toString rtpStartPort}"/>
        <param name="rtp-end-port" value="${toString rtpEndPort}"/>
      </settings>
    </configuration>
  '';

  "autoload_configs/sofia.conf.xml" = pkgs.writeText "sofia.conf.xml" ''
    <configuration name="sofia.conf" description="sofia Endpoint">
      <global_settings>
        <param name="log-level" value="0"/>
      </global_settings>
      <profiles>
        <!-- Deliberately explicit: no IPv6 profiles, no extra templates. -->
        <X-PRE-PROCESS cmd="include" data="../sip_profiles/internal.xml"/>
        <X-PRE-PROCESS cmd="include" data="../sip_profiles/external.xml"/>
      </profiles>
    </configuration>
  '';

  "autoload_configs/local_stream.conf.xml" = pkgs.writeText "local_stream.conf.xml" ''
    <configuration name="local_stream.conf" description="stream files from local dir">
      <directory name="default" path="${
        if soundsDir != null then "${soundsDir}/music/8000" else "/var/lib/freeswitch/empty-moh"
      }">
        <param name="rate" value="8000"/>
        <param name="shuffle" value="true"/>
        <param name="channels" value="1"/>
        <param name="interval" value="20"/>
        <param name="timer-name" value="soft"/>
      </directory>
      <directory name="moh/8000" path="${
        if soundsDir != null then "${soundsDir}/music/8000" else "/var/lib/freeswitch/empty-moh"
      }">
        <param name="rate" value="8000"/>
        <param name="shuffle" value="true"/>
        <param name="channels" value="1"/>
        <param name="interval" value="20"/>
        <param name="timer-name" value="soft"/>
      </directory>
    </configuration>
  '';

  "sip_profiles/internal.xml" = pkgs.writeText "internal.xml" ''
    <profile name="internal">
      <settings>
        <param name="context" value="default"/>
        <param name="dialplan" value="XML"/>
        <param name="sip-port" value="''$''${internal_sip_port}"/>
        <param name="rtp-ip" value="''$''${local_ip_v4}"/>
        <param name="sip-ip" value="''$''${local_ip_v4}"/>
        <param name="ext-rtp-ip" value="''$''${external_rtp_ip}"/>
        <param name="ext-sip-ip" value="''$''${external_sip_ip}"/>
        <param name="inbound-codec-prefs" value="''$''${global_codec_prefs}"/>
        <param name="outbound-codec-prefs" value="''$''${outbound_codec_prefs}"/>
        <param name="hold-music" value="''$''${hold_music}"/>
        <param name="rtp-timer-name" value="soft"/>
        <param name="rtp-timeout-sec" value="300"/>
        <param name="rtp-hold-timeout-sec" value="1800"/>
        <param name="apply-nat-acl" value="rfc1918"/>
        <param name="aggressive-nat-detection" value="true"/>
        <param name="auth-calls" value="''$''${internal_auth_calls}"/>
        <param name="auth-subscriptions" value="true"/>
        <param name="inbound-reg-force-matching-username" value="true"/>
        <param name="nonce-ttl" value="60"/>
        <param name="manage-presence" value="true"/>
        <param name="multiple-registrations" value="true"/>
        <param name="record-path" value="''$''${recordings_dir}"/>
        <!-- SIP over plain WebSocket; nginx terminates TLS and proxies here. -->
        <param name="ws-binding" value="${wsBindAddress}:${toString wsBindPort}"/>
        <!-- TLS transport for hard/soft SIP phones (self-signed per host). -->
        <param name="tls" value="''$''${internal_ssl_enable}"/>
        <param name="tls-sip-port" value="''$''${internal_tls_port}"/>
        <param name="tls-bind-params" value="transport=tls"/>
        <param name="tls-version" value="''$''${sip_tls_version}"/>
        <param name="tls-verify-policy" value="none"/>
        ${optionalString (tlsCertDir != null) ''
          <!-- Certificates provisioned from ACME (agent.pem + cafile.pem). -->
          <param name="tls-cert-dir" value="${tlsCertDir}"/>
        ''}
      </settings>
    </profile>
  '';

  "sip_profiles/external.xml" = pkgs.writeText "external.xml" ''
    <profile name="external">
      <!-- Outbound-only profile: hosts the ITSP gateway and receives its calls. -->
      <gateways>
        ${gatewayXml}
      </gateways>
      <settings>
        <param name="context" value="public"/>
        <param name="dialplan" value="XML"/>
        <param name="sip-port" value="''$''${external_sip_port}"/>
        <param name="rtp-ip" value="''$''${local_ip_v4}"/>
        <param name="sip-ip" value="''$''${local_ip_v4}"/>
        <param name="ext-rtp-ip" value="''$''${external_rtp_ip}"/>
        <param name="ext-sip-ip" value="''$''${external_sip_ip}"/>
        <param name="inbound-codec-prefs" value="''$''${global_codec_prefs}"/>
        <param name="outbound-codec-prefs" value="''$''${outbound_codec_prefs}"/>
        <param name="hold-music" value="''$''${hold_music}"/>
        <param name="rtp-timer-name" value="soft"/>
        <param name="rtp-timeout-sec" value="300"/>
        <param name="aggressive-nat-detection" value="true"/>
        <!-- Inbound ITSP INVITEs are typically unauthenticated (IP-based trust).
             With gateway.allowedCidrs set, trust only the provider's
             addresses via the ACL; otherwise rely on the firewall. -->
        <param name="auth-calls" value="false"/>
        <param name="apply-inbound-acl" value="${
          if gatewayAllowedCidrs == [ ] then "none" else inboundAclName
        }"/>
      </settings>
    </profile>
  '';

  "directory/default.xml" = pkgs.writeText "directory-default.xml" ''
    <include>
      <domain name="''$''${domain}">
        <params>
          <param name="dial-string" value="{presence_id=''$''${dialed_user}@''$''${dialed_domain}}''$''${sofia_contact(*/''$''${dialed_user}@''$''${dialed_domain})}"/>
        </params>
        <groups>
          <group name="default">
            <users>
              ${concatStrings (lib.mapAttrsToList userXml extensions)}
            </users>
          </group>
        </groups>
      </domain>
    </include>
  '';

  "dialplan/default.xml" = pkgs.writeText "dialplan-default.xml" ''
    <include>
      <context name="default">
        <extension name="loop_guard">
          <condition field="''${sip_looped_call}" expression="^true$">
            <action application="hangup"/>
          </condition>
        </extension>

        <extension name="echo_test">
          <condition field="destination_number" expression="^(9196)$">
            <action application="answer"/>
            <action application="echo"/>
          </condition>
        </extension>

        <extension name="voicemail_check">
          <condition field="destination_number" expression="^\*98$">
            <action application="answer"/>
            <action application="voicemail" data="check default ''$''${domain}"/>
          </condition>
        </extension>

        ${concatStrings (lib.mapAttrsToList ringGroupEntry ringGroups)}

        ${concatStrings (lib.mapAttrsToList extensionDialplanEntry extensions)}

        ${pstnEntry}

        <extension name="catch_all">
          <condition field="destination_number" expression="^.*$">
            <action application="hangup" data="unallocated_number"/>
          </condition>
        </extension>
      </context>
    </include>
  '';

  "dialplan/public.xml" = pkgs.writeText "dialplan-public.xml" ''
    <include>
      <context name="public">
        ${optionalString (gateway != null) ''
          <extension name="public_did">
            <condition field="destination_number" expression="^\+?${escapeXML gateway.did}$">
              <action application="transfer" data="${escapeXML gateway.didDestination} XML default"/>
            </condition>
          </extension>
        ''}
        <extension name="public_reject">
          <condition field="destination_number" expression="^.*$">
            <action application="hangup" data="unallocated_number"/>
          </condition>
        </extension>
      </context>
    </include>
  '';
}
