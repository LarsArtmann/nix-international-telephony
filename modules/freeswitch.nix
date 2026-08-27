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
  # ITSP trunks keyed by gateway name:
  #   itsp = { proxy, realm, username, password, register, priority,
  #            allowedCidrs, callerIdNumber, did, didDestination,
  #            dialPrefix, fromUser, fromDomain }
  # Outbound calls try gateways in ascending priority (least-cost routing).
  gateways ? { },
  # IVR menus keyed by name: <name> = { extension, greetingSound,
  #   invalidSound, timeoutSec, maxTries, entries.<key>.destination,
  #   fallbackDestination }.
  ivrs ? { },
  # Conference rooms keyed by name: <name> = { extension, profile, pin }.
  conferences ? { },
  # Event socket (fs_cli) password. Listens on 127.0.0.1 only.
  eventSocketPassword,
  recordingsDir ? "/var/lib/freeswitch/recordings",
  enableRecording ? true,
  cdrLogBase ? "/var/lib/freeswitch",
  enableCdr ? false,
  rtpStartPort ? 16384,
  rtpEndPort ? 16584,
  # Public IPs advertised in SDP/SIP when the PBX sits behind NAT; null =
  # use the local address ("$${local_ip_v4}" resolved by FreeSWITCH).
  natSipAddress ? null,
  natRtpAddress ? null,
  # Secure-WS SIP transport consumed by the nginx TLS proxy. MUST be wss,
  # not plain ws: browsers only speak wss:// from https pages, so SIP.js
  # always sends Via/2.0/WSS — and FreeSWITCH silently drops requests whose
  # Via transport token does not match the connection transport. nginx
  # therefore terminates the browser's wss and re-origins TLS to this
  # binding, keeping the transport token consistent end to end.
  wssBindAddress ? "127.0.0.1",
  wssBindPort ? 7443,
  # Certificate directory for SIP-over-TLS when the operator provisions one
  # (e.g. from ACME); sofia reads agent.pem (cert+key) and cafile.pem from
  # here. null = FreeSWITCH self-generates its usual certificates.
  tlsCertDir ? null,
}:

let
  inherit (lib)
    concatStrings
    concatStringsSep
    escapeXML
    optionalString
    ;

  externalSipIp = if natSipAddress != null then natSipAddress else "$\${local_ip_v4}";
  externalRtpIp = if natRtpAddress != null then natRtpAddress else "$\${local_ip_v4}";
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
        <param name="vm-password" value="${escapeXML user.vmPassword}"/>${
          optionalString (
            user ? vmEmail && user.vmEmail != null
          ) ''<param name="vm-mailto" value="${escapeXML user.vmEmail}"/>''
        }
      </params>
      <variables>
        <variable name="toll_allow" value="${
          if user.allowInternational then "domestic,international,local" else "domestic,local"
        }"/>
        <variable name="accountcode" value="${number}"/>
        <variable name="user_context" value="default"/>
        <variable name="effective_caller_id_name" value="${escapeXML user.displayName}"/>
        <variable name="effective_caller_id_number" value="${number}"/>
        ${optionalString (firstGateway != null) ''
          <variable name="outbound_caller_id_name" value="${
            escapeXML (
              if user ? callerIdNumber && user.callerIdNumber != null then
                user.callerIdNumber
              else
                firstGateway.callerIdNumber
            )
          }"/>
          <variable name="outbound_caller_id_number" value="${
            escapeXML (
              if user ? callerIdNumber && user.callerIdNumber != null then
                user.callerIdNumber
              else
                firstGateway.callerIdNumber
            )
          }"/>''}
      </variables>
    </user>
  '';

  extensionActions = number: record: ''
    <action application="set" data="hangup_after_bridge=true"/>
    <action application="set" data="continue_on_fail=true"/>
    <action application="set" data="originate_timeout=30"/>
    ${optionalString record (recordingActions number)}
    <action application="bridge" data="user/${number}"/>
    <action application="answer"/>
    <action application="sleep" data="1000"/>
    <action application="voicemail" data="default ''$''${domain} ${number}"/>
  '';

  # *97<number>: place the call with per-call recording SKIPPED (only
  # generated when recording is on by default — see options.nix).
  extensionDialplanEntry =
    number: _:
    ''
      <extension name="extension_${number}">
        <condition field="destination_number" expression="^${number}$">
        ${extensionActions number true}
        </condition>
      </extension>
    ''
    + optionalString enableRecording ''
      <extension name="extension_norecord_${number}">
        <condition field="destination_number" expression="^\*97${number}$">
        ${extensionActions number false}
        </condition>
      </extension>
    '';

  # Ring-group dialplan body, shared by the plain and time-routed forms.
  ringGroupActions = number: group: record: ''
    <action application="set" data="ringback=''$''${us-ring}"/>
    <action application="set" data="hangup_after_bridge=true"/>
    <action application="set" data="continue_on_fail=true"/>
    <action application="set" data="originate_timeout=${toString group.timeoutSec}"/>
    ${optionalString record (recordingActions number)}
    <action application="bridge" data="${
      lib.concatStringsSep "," (map (m: "user/${m}") group.members)
    }"/>
    <action application="answer"/>
    <action application="sleep" data="1000"/>
    <action application="voicemail" data="default ''$''${domain} ${group.voicemailMember}"/>
  '';

  # Time-of-day routing on FreeSWITCH's date-time condition attributes
  # (verified against switch_xml_std_datetime_check: wday is 1=Sun..7=Sat,
  # hour/minute-of-day take switch_number_cmp ranges like "9-17").
  wdayNumbers = {
    sun = 1;
    mon = 2;
    tue = 3;
    wed = 4;
    thu = 5;
    fri = 6;
    sat = 7;
  };
  wdayRange = days: lib.concatStringsSep "," (map (d: toString wdayNumbers.${d}) days);
  hourRange = group: "${toString group.timeWindow.startHour}-${toString group.timeWindow.endHour}";
  # complement of start-end in 0..23 (endHour inclusive -> out after it)

  ringGroupEntry =
    number: group:
    (
      if group.timeWindow.afterHoursDestination != null then
        ''
          <extension name="ring_group_${number}">
            <condition field="destination_number" expression="^${number}$">
              <condition wday="${wdayRange group.timeWindow.days}" hour="${hourRange group}" break="on-true">
          ${ringGroupActions number group true}
              </condition>
              <condition break="never">
                <action application="transfer" data="${escapeXML group.timeWindow.afterHoursDestination} XML default"/>
              </condition>
            </condition>
          </extension>
        ''
      else
        ''
          <extension name="ring_group_${number}">
            <condition field="destination_number" expression="^${number}$">
          ${ringGroupActions number group true}
            </condition>
          </extension>
        ''
    )
    + optionalString enableRecording ''
      <extension name="ring_group_norecord_${number}">
        <condition field="destination_number" expression="^''\\*97${number}$">
      ${ringGroupActions number group false}
        </condition>
      </extension>
    '';

  # Conference room: bridge the caller straight into mod_conference
  # (vanilla conference.conf.xml provides the profiles; the module is in
  # our load list). With a pin, mod_conference prompts for it on entry.
  conferenceEntry =
    name: conf:
    let
      pinSuffix = if conf.pin != null then "+${conf.pin}" else "";
    in
    ''
      <extension name="conference_${escapeXML name}">
        <condition field="destination_number" expression="^${conf.extension}$">
          <action application="answer"/>
          <action application="conference" data="${escapeXML name}@${escapeXML conf.profile}${pinSuffix}"/>
        </condition>
      </extension>
    '';

  # IVR menu: answer, play the greeting, collect a #-terminated key with
  # play_and_get_digits (which re-prompts on invalid input up to
  # maxTries), then route via nested conditions. The final
  # break="never" condition guarantees termination: mapped key, fallback
  # destination, or hangup. Destinations run through transfer so the
  # full dialplan (extension, ring group, PSTN, echo) applies.
  ivrEntry =
    name: ivr:
    let
      inputVar = "ivr_input_${name}";
      entryConditions = concatStrings (
        lib.mapAttrsToList (key: entry: ''
          <condition field="''${${inputVar}}" expression="^${escapeXML key}$">
            <action application="transfer" data="${escapeXML entry.destination} XML default"/>
          </condition>
        '') ivr.entries
      );
      fallbackActions =
        if ivr.fallbackDestination != null then
          ''<action application="transfer" data="${escapeXML ivr.fallbackDestination} XML default"/>''
        else
          ''<action application="hangup" data="call_rejected"/>'';
    in
    ''
      <extension name="ivr_${escapeXML name}">
        <condition field="destination_number" expression="^${ivr.extension}$">
          <action application="answer"/>
          <action application="sleep" data="500"/>
          <action application="set" data="hangup_after_bridge=true"/>
          <action application="set" data="continue_on_fail=true"/>
          ${recordingActions ivr.extension}
          <action application="play_and_get_digits" data="1 16 ${toString ivr.maxTries} # ${
            toString (ivr.timeoutSec * 1000)
          } ${escapeXML ivr.greetingSound} ${escapeXML ivr.invalidSound} ${inputVar} ^[0-9]+$"/>
          ${entryConditions}
          <condition break="never" field="''${${inputVar}}" expression="^.*$">
            ${fallbackActions}
          </condition>
        </condition>
      </extension>
    '';

  gatewayList = lib.mapAttrsToList (name: g: g // { inherit name; }) gateways;
  # Least-cost routing: ascending priority, then name for determinism.
  gatewaysByPriority = lib.sortOn (g: "${lib.fixedWidthNumber 5 g.priority} ${g.name}") gatewayList;
  firstGateway = if gatewaysByPriority == [ ] then null else builtins.head gatewaysByPriority;
  hasGateways = gateways != { };

  gatewayXml = concatStrings (
    map (g: ''
      <gateway name="${escapeXML g.name}">
        <param name="username" value="${escapeXML g.username}"/>
        <param name="password" value="${escapeXML g.password}"/>
        <param name="proxy" value="${escapeXML g.proxy}"/>
        <param name="realm" value="${escapeXML g.realm}"/>
        <param name="register" value="${lib.boolToString g.register}"/>
        ${optionalString (g.fromUser != null) ''
          <param name="from-user" value="${escapeXML g.fromUser}"/>
          <param name="from-domain" value="${escapeXML g.fromDomain}"/>
        ''}
      </gateway>
    '') gatewayList
  );

  # Name of the inbound ACL on the external profile when the operator
  # listed the provider's source addresses.
  inboundAclName = "trusted-itsp";

  # ACL nodes from every gateway's allowedCidrs; omitted entirely when
  # unconfigured (the package's vanilla acl.conf.xml stays in place then).
  gatewayAllowedCidrs = lib.unique (lib.concatLists (map (g: g.allowedCidrs) gatewayList));

  # Sequential failover across gateways in priority order ("|" is serial
  # bridging: the next gateway is only tried when the previous fails).
  lcrBridge = concatStringsSep "|" (
    map (g: "sofia/gateway/${escapeXML g.name}/${escapeXML g.dialPrefix}$1") gatewaysByPriority
  );

  pstnEntry =
    if hasGateways then
      ''
        <extension name="pstn_international">
          <condition field="''${toll_allow}" expression="international"/>
          <condition field="destination_number" expression="^\+?([1-9]\d{7,14})$">
            <action application="set" data="effective_caller_id_number=''${outbound_caller_id_number}"/>
            <action application="set" data="effective_caller_id_name=''${outbound_caller_id_name}"/>
            ${recordingActions "pstn"}
            <action application="bridge" data="${lcrBridge}"/>
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
      <X-PRE-PROCESS cmd="set" data="external_rtp_ip=${externalRtpIp}"/>
      <X-PRE-PROCESS cmd="set" data="external_sip_ip=${externalSipIp}"/>
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
        <!-- Secure WebSocket for the webphone; nginx terminates the browser's
             wss and proxies here over TLS (see modules/telephony/web.nix —
             a plain ws-binding drops the browser's Via/WSS REGISTERs). -->
        <param name="wss-binding" value="${wssBindAddress}:${toString wssBindPort}"/>
        <!-- WebRTC ICE candidate screening: without this sofia screens
             candidates against wan.auto, which DENIES all private ranges —
             every LAN/LAB browser (no srflx candidates) then gets its
             INVITE rejected with 488 INCOMPATIBLE_DESTINATION. -->
        <param name="apply-candidate-acl" value="localnet.auto"/>
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
          <!-- Dial-time template for user/<ext> bridging. dialed_user/
               dialed_domain are RUNTIME dial variables: single-dollar
               braces like vanilla, NOT doubled pre-processor vars
               (over-escaping them breaks every user/N bridge with
               "No origination URL specified"). The wildcard profile
               searches all profiles for the contact so any transport
               (udp/tcp/ws/wss) resolves. -->
          <param name="dial-string" value="{presence_id=''${dialed_user}@''${dialed_domain}}''${sofia_contact(*/''${dialed_user}@''${dialed_domain})}"/>
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

        ${concatStrings (lib.mapAttrsToList ivrEntry ivrs)}

        ${concatStrings (lib.mapAttrsToList conferenceEntry conferences)}

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
        ${concatStrings (
          map (g: ''
            <extension name="public_did_${escapeXML g.name}">
              <condition field="destination_number" expression="^\+?${escapeXML g.did}$">
                <action application="transfer" data="${escapeXML g.didDestination} XML default"/>
              </condition>
            </extension>
          '') gatewayList
        )}
        <extension name="public_reject">
          <condition field="destination_number" expression="^.*$">
            <action application="hangup" data="unallocated_number"/>
          </condition>
        </extension>
      </context>
    </include>
  '';
}
