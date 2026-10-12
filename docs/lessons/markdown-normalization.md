# Formatter-over-archives: the markdown normalization incident class

Long-form background for the AGENTS.md marker conventions and the
`markers_check` / `rendering_audit` gates. Everything here was learned
the hard way between 2026-09-29 and 2026-10-12; this file is the
one home for the mechanics, so AGENTS.md can stay compressed.

## The three incidents

1. **`5ba5d2b` (2026-09-29) — the verdict-column drop.** A table
   normalization pass re-wrapped an archived snapshot's §b table and
   dropped the verdict COLUMN from four rows outright. The content
   sweep did not see it: one row still carried a prose arrow that
   masked the loss. The file-level monotonicity arm (shipped the same
   week) caught it from git history; the repair was in-cell
   `→ done — …` appends, immune to later column re-normalization.
2. **`04562e787` (2026-09-29) — the fence destruction.** A strike TAIL
   at line start (leading `~~~`) of the round-2 advisory report was
   normalized into a fenced code block. Every marker still counted —
   the content sweep stayed green — but the strikethrough RENDERED as
   code. Repaired in a fence-immune shape (`~~ ~2.2x …`); marker count
   recovered 135 → 137 against the historical peak 136.
3. **webphone-ui row 36 (found 2026-10-12) — the partial repair.** A
   post-archive normalization dropped the verdict CELL
   (`→ **Won't implement — …`, two markers) from one row; the same-day
   repair restored only the arrow (count 2 → 0 → 1). The file-level
   arm was satisfied because OTHER rows' repairs recovered the FILE
   peak. The per-item monotonicity arm (shipped 2026-10-12) flagged the
   residue; the fix was the house `→ corrected` append restoring the
   missing `Won't implement` marker with an honest correction note.

The class: formatters and normalization passes (treefmt/prettier over
markdown, editor rewraps, daemon-shipped formatted intermediates) are
marker-count-preserving but rendering-hostile, and repairs can
themselves be incomplete in ways only a finer-grained net catches.

## CommonMark/GFM semantics behind the damage

- **A line starting with `~~~` IS a fence opener.** Any verdict text
  that can wrap so that three tildes land at line start will one day
  render as a code block. Keep strike content fence-immune: never let
  `~~`-run into `~~~`, and prefer repairs that put the tilde run
  inside a code span (`~~ ~2.2x …`) or after a word.
- **GFM strikethrough cannot cross paragraph boundaries** (blank
  lines, headings, list/table starts). Multi-line strikes INSIDE one
  list item are legal; that is why per-line `~~` parity is a false
  positive machine — parity only means something at boundaries.
- **Inline code spans make their content literal.** A `~~` inside
  backticks is text, not a delimiter — repairs exploit this, and
  audits must strip code spans before counting.
- Prettier and friends re-wrap TABLES to normalize column widths. Any
  verdict living in a table cell moves through many byte-identical-in-
  meaning rewrites; column drops are the 5ba5d2b shape.

## Recovery-by-append grammar

A stale or damaged verdict is NEVER rewritten. The remedy is an
append: `→ corrected <date> — <what happened>` (or re-striking the
damaged tail in a fence-immune shape when rendering died). Appends
grow the marker count, which is exactly what clears the monotonicity
arms — "count recovery" and "honest history" are the same operation.
Rewriting instead of appending is how incident 3's partial repair hid
for three weeks.

## Mechanism deviation: pickaxe → follow + per-revision counts

The monotonicity arm was originally sketched as a git pickaxe sweep
(`git log -S<marker>`) counting introduce/remove EDGES. That cannot
express the actual invariant — "lost and never repaired back to the
peak" — because edges do not compose into a peak/recovery model. The
shipped mechanism walks `git log --follow --name-status` (renames
included), blobs each revision via `git show`, counts `MARKER_RE`
matches per revision, and tracks peak/recover over the sequence.
`--follow` is load-bearing: every archive lands via `git mv`, and the
chain must survive it. The per-item arm reuses the SAME walk (one
`git show` per revision feeds both arms) and slices to POST-ARCHIVE
revisions only — the pre-archive history is full of benign per-item
count drops (the 2026-08-22 verdict-twin dedup cleanup removed
duplicated stale verdicts from a dozen items while the snapshots were
still live), and policing legitimate annotation churn would drown the
real damage signal.

## Standing gates

- `python3 scripts/markers_check.py` — content sweep (every scoped
  item marked) + file-level monotonicity (whole history) + per-item
  monotonicity (post-archive only). `--self-test` carries the negative
  arms on synthetic repos.
- `python3 scripts/rendering_audit.py` — rendering classes the marker
  gates cannot see: line-start `~~~` fences, unclosed code fences,
  strikes open at paragraph boundaries, odd `**` parity in table rows.
  (Del-tag parity was tried and retired: the .md archives carry only
  prose MENTIONS of `<del>`, which parity cannot separate from real
  markup.)
- `go run ./assets/annotate.go check-rows <files>` (docs-health skill)
  — row-uniformity after every annotation pass, before archiving.

Run all three after any batch edit to archived snapshots; a repair
that drops any of them is not done.
