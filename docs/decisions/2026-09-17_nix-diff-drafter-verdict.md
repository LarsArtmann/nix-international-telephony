# Decision: Nix diff-drafter — Don't-build-now (revisit on trigger)

Date: 2026-09-17
Status: Decided (spike-level analysis; no code shipped)
Plan row: P22 (round-2 Pareto plan) — concept spike + build-or-drop verdict

## The idea, restated

An operator-window form (extension, ring group, IVR entry) that renders a
ready-to-paste `services.telephony.*` Nix snippet — a drafting aid, never
an applier. The window drafts; the flake stays the single config brain;
the operator copies the snippet into their config and rebuilds.

## Why it was on the table

The fspbx trial (docs/research/2026-09-16_fspbx-trial.md) showed a GUI that
mutates PBX state directly — convenient, but it makes the GUI a second
config brain and orphans the declarative config. A drafter was proposed as
the "window, not editor" answer to that convenience.

## Verdict: don't build now

1. **The pain it relieves is rare.** Config changes (new extension, ring
   group, IVR stanza) happen a few times a year at this deployment's
   scale. The module's option docs plus the dialplan simulator
   (`telephony-dialplan-simulate`, `/operator-api/simulate`) already
   answer "what do I write" and "what will it do".
2. **The form would still drift.** A hand-written field-to-snippet
   generator is a second encoder of the module's option surface. Every
   new option (fax, operator, contacts — three this quarter) would need
   a matching form field or the draft lies. Drifting drafts are worse
   than no drafts.
3. **The simulator already occupies the "window" niche.** It reads the
   generated dialplan at runtime — ground truth by construction. A
   snippet drafter reads nothing; it hallucinates from a template.
4. **The audience is thin.** The operator window serves an admin who
   watches state. This deployment's config author already writes Nix.

## Trigger conditions to revisit

- A second admin who does not write Nix needs to draft config, or
- config churn grows (e.g. the DE DID brings per-destination routing
  tables that change monthly), or
- the module's option surface stabilizes for 2+ quarters with a stable
  generator story (e.g. an option-schema JSON that a form could consume
  without hand-encoding).

If triggered, build it as a read-only `snippet` endpoint next to
`/api/simulate` in the operator package (stdlib template, no state, no
auth beyond the operator realm) — roughly a day, not a spike.
