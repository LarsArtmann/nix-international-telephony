> [!NOTE]
> This filing was drafted by GLM-5.3-flash via Crush from an AI-run investigation, not at my request. When the failure traces to an external report, that source is linked in the body.
>
> - [ ] MANUALLY REVIEWED by `@Lars Artmann` at `[<date-time>]`

**TL;DR:** usermgmt's WebAuthn begin endpoints serve the ceremony options nested under go-webauthn's `"publicKey"` key, while both JS consumers (`loginpage/assets/login.js`, webphone's enroll page) read `opts.challenge` at the top level — every real browser ceremony throws before any request leaves the page. Ask: unwrap (or shim), and pin the real wire in a test that opens the options object.

## Problem

The provider marshals go-webauthn's `*protocol.CredentialCreation` raw, and that struct nests the whole dictionary under `"publicKey"` (`Response PublicKeyCredentialCreationOptions \`json:"publicKey"\`` — stable across go-webauthn versions):

- `usermgmt/webauthn/provider.go:167-179` — `marshalCeremonyResponse` does `json.Marshal(options)` on the `CredentialCreation` → `{"publicKey":{...}}`
- `usermgmt/webauthn_service.go:69-72` — `webauthnBeginResponse{Options jsontext.Value}` carries those wrapped bytes as `options`
- `usermgmt/webauthn_http.go:48` and webphone `internal/server/passkey_api.go:189` — both `writeJSON(w, http.StatusOK, resp)` without unwrapping

Both JS sides read the top level:

- `loginpage/assets/login.js:68,79` — `p.challenge = b64uToBuf(opts.challenge)`; `b64uToBuf(undefined)` → `undefined.replace` TypeError
- webphone `internal/web/assets/enroll/webauthn.js` (`prepareRegistrationOptions` → `toBytes(options.challenge)` → `throw "expected base64url string, got undefined"`) and `enroll.js` maps it into its catch-all `"Network error — try again."` copy

So the enroll page shows a network error while the server logged 200s, and the login page fails the same way one line earlier.

## Evidence from a live ceremony

Webphone's passkey ceremony E2E (CDP virtual authenticator, real `/enroll` page) on webphone `e762f5af`: token verify 200, begin 200, `registration ceremony begun` in the journal — then nothing. No `finish` request ever reaches the server; the page's `#enroll-error` element carries the network copy within ~2s of submit. The throw happens between `begin`'s 200 and the `credentials.create` call, exactly where `prepareRegistrationOptions` decodes.

## Why the tests miss it

Three layers, mutually blind:

1. Go tests assert only `len(begun.Options) > 0` (webphone `internal/server/passkey_api_test.go:322-326`) — never open the options object
2. The JS tests stub the begin response FLAT (webphone `internal/web/assets/island-tests/enroll.test.mjs:55-64`: `options: { challenge: "AAAAAQ", ... }`) — the stub disagrees with the real wire
3. No browser-level test drives the real wire against the real provider

## What a fix looks like

Either side closes it: unwrap `.publicKey` in `marshalCeremonyResponse` (the provider owns the go-webauthn type knowledge, and `login.js` + `enroll.js` + both `.d.ts` shapes already agree on flat), or read `opts.publicKey ?? opts` in both consumers. A Go test that unmarshals `begun.Options` and asserts `challenge` is a string pins it either way.

Affects: go-cqrs-lite `usermgmt` + `loginpage`, webphone enroll page (both consumers at webphone `e762f5af`, go-cqrs-lite `2yv9f0v`-era source).

💘 Generated with Crush
