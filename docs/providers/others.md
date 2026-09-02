# Others (briefly considered, dismissed for this use case)

Providers evaluated at a glance during the 2026-08 provider survey.
None warrant a full file today; revisit triggers noted per entry.

| Provider                                               | Why dismissed                                                                                                                                                  | Revisit when                                                                                            |
| ------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| **Flowroute**                                          | US/CA-focused trunking; international DID inventory far smaller than Telnyx/DIDWW                                                                              | A US-only calling product needs a second US trunk                                                       |
| **VoIP.ms**                                            | US/CA only                                                                                                                                                     | Same as Flowroute                                                                                       |
| **Skyetel**                                            | US/CA only, hobbyist-friendly                                                                                                                                  | Same                                                                                                    |
| **Voxtelesys**                                         | US/CA + some international fax/SMS; not a 5-country voice play                                                                                                 | US SMS/fax needs                                                                                        |
| **sipgate** (DE)                                       | German consumer/business ITSP with attractive pricing and easy German KYC — but no CH/PL/HK/US DIDs; trunk features are registration-based and consumer-shaped | A dedicated _German-only_ number project where consumer-grade KYC wins; could complement the main trunk |
| **Easybell** (DE)                                      | Same profile as sipgate (DE-only, consumer/business)                                                                                                           | Same                                                                                                    |
| **AVOXI / United World Telecom / HotTelecom / Freeje** | Virtual-number resellers oriented to call forwarding, not raw SIP trunking into an owned PBX; ❓ none verified                                                 | Never for trunking; possibly for disposable presence numbers                                            |

Also deliberately out of scope: **messaging-first CPaaS** (Twilio
Messaging, Telnyx Messaging, MessageBird/Vonage) — the PBX is
voice-only today; pick a messaging API when a concrete SMS/WhatsApp
requirement exists, not before.
