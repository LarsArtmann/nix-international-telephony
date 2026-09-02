# Domain Language

> The ubiquitous language of this project. Every term used in code,
> conversations, and docs should be defined here unambiguously.

## Core terms

| Term            | Definition                                                                                                                                                   | Where used in code                                                                                            |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------- |
| Extension       | A SIP user account (directory entry) keyed by a 2-7 digit number; registers a phone and receives calls                                                       | `extensions` option, `extensionType` (`modules/telephony/options.nix`)                                        |
| Ring group      | A virtual number that rings several extensions simultaneously, falling back to a member's voicemail                                                          | `ringGroups` option, `ringGroupEntry` (`modules/freeswitch.nix`)                                              |
| Gateway         | A named ITSP trunk definition (SIP proxy, credentials, outbound prefix, inbound DID); outbound calls fail over across gateways in ascending `priority` (LCR) | `gateways` option (attrsOf), `gatewayType`, `gatewayXml`; the singular `gateway` option is a deprecated alias |
| ITSP            | Internet Telephony Service Provider — the company terminating PSTN calls for the gateway                                                                     | README, gateway option descriptions                                                                           |
| DID             | Direct Inbound Dialling number — the public number the provider sends to the `external` profile                                                              | `gateways.<name>.did`, `public_did` dialplan extension                                                        |
| DID destination | Extension or ring group that answers calls to the DID                                                                                                        | `gateways.<name>.didDestination`                                                                              |
| Dialplan        | FreeSWITCH's routing rules deciding what happens to a dialled number                                                                                         | `dialplan/default.xml`, `dialplan/public.xml`                                                                 |
| Context         | Dialplan partition selected per call origin: `default` (authenticated users) vs `public` (inbound ITSP)                                                      | `user_context` variable, profile `context` params                                                             |
| Toll allow      | Per-extension permission string gating international dialling (`domestic,international,local`)                                                               | `allowInternational` option, `toll_allow` variable                                                            |
| Realm           | SIP authentication realm; for a gateway it defaults to the proxy host                                                                                        | `gateways.<name>.realm`, coturn `realm`                                                                       |
| Registration    | A SIP phone's REGISTER binding letting FreeSWITCH reach it; multiple devices per extension allowed                                                           | `multiple-registrations` in `internal.xml`                                                                    |
| Event socket    | Local-only TCP control interface (port 8021) driven by `fs_cli`                                                                                              | `event_socket.conf.xml`, `eventSocketPassword` option                                                         |
| Webphone        | The static SIP.js browser softphone served at `https://<domain>/`                                                                                            | `packages/webphone/`, `webphone.*` options                                                                    |
| `config.js`     | Generated script handing the webphone its SIP domain and STUN/TURN ICE servers                                                                               | `modules/telephony/web.nix`                                                                                   |
| NAT address     | Public IP advertised in SIP/SDP when the PBX sits behind NAT                                                                                                 | `natAddress` option, `external_rtp_ip`/`external_sip_ip` vars                                                 |
| RTP port range  | UDP port interval reserved for call media (~2 ports per leg)                                                                                                 | `rtp.startPort`/`rtp.endPort`, `switch.conf.xml`                                                              |
| MOH             | Music on hold, streamed from the sounds package via `local_stream`                                                                                           | `hold_music` var, `local_stream.conf.xml`                                                                     |
| Sounds package  | FreeSWITCH prompt set (en/us/callie) plus MOH archive, 8 kHz                                                                                                 | `packages/sounds.nix`, `sounds.package` option                                                                |
| Voicemail box   | Per-extension message store with a numeric PIN; checked by dialling `*98`                                                                                    | `vmPassword` option, voicemail dialplan entries                                                               |
| Echo test       | Diagnostic extension `9196` that reflects audio back to the caller                                                                                           | `echo_test` dialplan extension                                                                                |
| Recording       | Per-call WAV capture via `record_session` into the shared `/var/lib/telephony/recordings` dir (nginx-servable)                                               | `recording.enable` option, `recordingActions`                                                                 |
| Demo VM         | Ephemeral QEMU appliance built from `hosts/pbx` via `nix run .#vm`                                                                                           | `apps.vm` (`flake.nix`), `hosts/pbx/`                                                                         |

## Bounded contexts

Terms that carry different meanings in different parts of the system:

| Term      | FreeSWITCH/XML context                                                                            | Module/domain context                                   |
| --------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Extension | A dialplan `<extension>` element — a routing _rule_ (e.g. `extension_1000`, `pstn_international`) | A SIP _user_ — the directory account phones register as |
| Internal  | Sofia profile serving registered users (5060/5061 + loopback wss 7443 for the webphone)           | `internal_*` pre-processor variables in `vars.xml`      |
| External  | Sofia profile hosting the ITSP gateways and inbound provider calls (5080, context `public`)       | —                                                       |
| Trunk     | Synonym of Gateway in telephony speech                                                            | Code consistently uses **gateway** only                 |

## Deprecated terms

None yet — the vocabulary is young and consistent.
