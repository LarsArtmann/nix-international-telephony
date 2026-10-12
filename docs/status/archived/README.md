# Archive manifest — docs/status

Closed history. Every file here carries inline resolution markers on all
scoped items (`~~…~~ done at`, `→ done/open/routed`, `Won't implement`,
`NOT-DO`) and passed `scripts/markers_check.py` (per-item + monotonicity
arms) plus the annotate.go `check-rows` uniformity pass at archive time.
Do not reopen resolved work; read only for provenance.

## Bulk sweep manifests

**2026-10-12 docs-health round 10** (annotated + archived in one sweep):

| File                                                                   | Classification     | Deciding reason                                                                                                                                                                                                               |
| ---------------------------------------------------------------------- | ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `2026-09-30_12-22_markers-monotonicity-arm-session-status.md`          | ANNOTATE → ARCHIVE | §b/§c/§f/§g fully resolved: follow-ups routed to TODO_LIST Low rows + ROADMAP docs-gate cluster; WhatsApp B-rows shipped 2026-09-30; §g1 resolved in force (formatter scope), §g3 superseded (CI runs the full gate per push) |
| `2026-09-30_12-35_docs-health-round9-harvest-archive-live-ci-truth.md` | ANNOTATE → ARCHIVE | Harvest rows shipped (CHANGELOG 2026-09-30); lock-tail verdict paid (run 36714029522); §b.1 appends landed; §g2 resolved by the lock-guard shipping; owner lanes route to standing TODO rows                                  |
