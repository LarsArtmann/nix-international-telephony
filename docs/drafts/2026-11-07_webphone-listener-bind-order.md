Title: HTTP listener binds only after the app container finishes starting — webhook consumers race the boot

> [!NOTE]
> This filing was drafted by GLM (via Crush) from an AI-run investigation, not at my request.
>
> - [ ] MANUALLY REVIEWED by `@Lars Artmann` at `[<date-time>]`

TL;DR: `cmd/webphone/main.go` starts the application container before it binds the HTTP listener, so a client that POSTs a webhook the moment the process is announced (systemd unit up, container started) races the boot work and gets a connection refused — indistinguishable from "wrong port". Binding the listener first and answering 503 until the container is ready would kill the class at the source; today every webhook consumer has to poll the port itself.

## Problem

At webphone `36f0c6f4a374a30f`, the boot sequence in `cmd/webphone/main.go` is:

```go
application, err := app.New(cfg, slog.Default())
if err := application.Start(ctx); err != nil { ... } // read model starts FIRST

httpServer, err := httputil.NewServer(httputil.ServerConfig{...}, application.Handler)
errCh := httpServer.Start() // listener binds LAST
```

Everything `application.Start` does (read-model replay included) happens before the port exists. A webhook producer — our Telnyx messaging bridge POSTs `POST /hooks/message` the moment its own unit is up — that fires in that window gets a TCP connection refused, not a 503. Connection refused is indistinguishable from a misconfigured port, so consumers cannot tell "transient boot" from "broken".

Hit for real in the consumer stack's NixOS VM suite: a unit-level wait on `webphone.service` alone raced the first bridge POST into a bridge-side failure under a loaded full `nix flake check` (once, load-dependent, never on an idle host — which is what makes it nasty to triage). Both consumers now poll the port before their first POST, which works but duplicates the workaround in every webhook client.

## Why binding first fixes it

With the listener bound before `application.Start` and a readiness gate on the app routes (503 until the container reports ready), a boot-window POST gets an honest 503 and the producer's retry does the right thing. The probe split already exists — `/livez` answers 200 always (liveness does no checks, `internal/server/probes_test.go`) while `/startupz` and `/healthz` do the checking — the boot order just doesn't lean on it yet.

## Scope

Anyone driving webhooks into `/hooks/*` from a second process started in parallel with webphone (systemd `Wants=` without a port-conditioned `After=`, container orchestration without a port probe). Interactive use is unaffected — by the time a human clicks, the boot has long finished.

💘 Generated with Crush
