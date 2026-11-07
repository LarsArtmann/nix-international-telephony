#!/usr/bin/env python3
"""Export this repo's EventCatalog source tree (inbound call routing).

Contract (hub: `eventcatalog-hub` build.sh + merge.py + lint-sources.sh,
verified against that repo's frontmatter schema v2 on 2026-11-06):

- Invoked as ``python3 scripts/export-catalog.py -o <tree>`` from the clone
  root. NEVER as ``./scripts/...``: CI clone dirs are NOEXEC and only the
  interpreter from PATH executes.
- Emits ONLY ``users/lars.mdx``, ``domains/telephony/index.mdx``,
  ``services/<id>/index.mdx``, ``events/<id>/index.mdx`` (+
  ``schemas/schema.json``), ``flows/<id>/index.mdx`` and
  ``adrs/<id>/index.mdx``. No ``catalog.index.json`` (manifest-free
  sources render "-" in error insights), no bootstrap files (the hub owns
  them), no badges (deployment chips union in from the SystemNix
  inventory tree as a DERIVED source at merge time).
- Per-source governance lint runs IN ISOLATION: ``owner-required``,
  ``summary-required``, ``refs/file-exists`` and
  ``structure/duplicate-resource-ids`` are ERROR severity, while
  ``refs/resource-exists`` is warn (cross-source refs resolve only in the
  merged union). Every resource below therefore names an owner, a summary,
  and only refs this tree itself provides.
- ``version`` is LOCKSTEP with the hub's render-inventory.py (hardcoded
  1.0.0): a mismatch forks an id's version set in the union.  That is why
  ``services/pbx`` is version 1.0.0 — the id is shared with the platform
  inventory row and this body supersedes its stub (authored bodies beat
  derived deployment facts, merge.py role policy).
- ``domains/telephony`` joins the domain pbx-lens already declares: the
  body stays first-wins (pbx-lens is merged before this source), while the
  ``services:`` membership list UNIONS across sources (merge.py), so the
  routing services appear on the domain page without touching that source.
- Deterministic: fixed data, fixed order, no timestamps — byte-stable
  across runs (the hub retries export jobs and diffs trees).
- Stdlib only (same contract as merge.py / render-inventory.py): the hub's
  python3 is a bare runner-PATH interpreter, no venv.

Usage:
  export-catalog.py -o <outdir>            # write tree (idempotent)
  export-catalog.py -o <outdir> --plain    # same tree; lint-tree parity
                                           # flag (no versioned outgoing
                                           # refs exist to strip)
  export-catalog.py -o <outdir> --check    # verify an existing tree is
                                           # byte-current (exit 1 = stale)
  export-catalog.py --selftest             # golden test, no repo needed
"""

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

from catalog_content import ADRS, DOMAIN, EVENTS, FLOWS, SERVICES

# LOCKSTEP with hub scripts/render-inventory.py ("version: 1.0.0").
RESOURCE_VERSION = "1.0.0"
OWNER = "lars"
REPOSITORY = "https://github.com/LarsArtmann/nix-international-telephony"

SAFE_SCALAR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._/@()+-]*$")
ADR_STATUSES = ("proposed", "accepted", "rejected", "deprecated", "superseded")


def yaml_str(value):
    """Quote a frontmatter scalar only when YAML would misparse it.

    Same contract as the hub's render-inventory.py: bare unless needed;
    anything with a ``: `` (or a trailing colon, or a leading special, or
    non-ASCII) rides as a JSON string, which is a valid YAML double-quoted
    scalar.
    """
    text = str(value)
    if SAFE_SCALAR_RE.match(text) and ": " not in text and not text.endswith(":"):
        return text
    return json.dumps(text, ensure_ascii=False)


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


def render_user():
    return """---
id: lars
name: Lars Artmann
email: git@lars.software
---

# Lars Artmann
"""


def render_domain():
    lines = [
        "---",
        f"id: {DOMAIN['id']}",
        f"name: {DOMAIN['name']}",
        f"version: {RESOURCE_VERSION}",
        f"summary: {yaml_str(DOMAIN['summary'])}",
        "owners:",
        f"    - {OWNER}",
        "services:",
    ]
    lines += [f"    -   id: {sid}" for sid in DOMAIN["services"]]
    lines += ["---"]
    return "\n".join(lines) + "\n" + DOMAIN["body"]


def render_service(svc):
    lines = [
        "---",
        f"id: {svc['id']}",
        f"name: {yaml_str(svc['name'])}",
        f"version: {RESOURCE_VERSION}",
        f"summary: {yaml_str(svc['summary'])}",
        "owners:",
        f"    - {OWNER}",
        "repository:",
        "    language: nix",
        f"    url: {REPOSITORY}",
    ]
    for key in ("receives", "sends"):
        ids = svc.get(key)
        if not ids:
            continue
        lines.append(f"{key}:")
        lines += [f"    -   id: {rid}" for rid in ids]
    lines += ["---"]
    return "\n".join(lines) + "\n\n# " + svc["name"] + "\n" + svc["body"]


def render_event(evt):
    lines = [
        "---",
        f"id: {evt['id']}",
        f"name: {yaml_str(evt['name'])}",
        f"version: {RESOURCE_VERSION}",
        f"summary: {yaml_str(evt['summary'])}",
        "owners:",
        f"    - {OWNER}",
        "producers:",
        f"    - {evt['producer']}",
        "schemaPath: schemas/schema.json",
        "---",
    ]
    return "\n".join(lines) + "\n\n# " + evt["name"] + "\n" + evt["body"]


def render_event_schema(evt):
    schema = dict(evt["schema"])
    ordered = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": evt["name"],
        "description": evt["summary"],
    }
    ordered.update(schema)
    return json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"


def render_flow(flow):
    lines = [
        "---",
        f"id: {flow['id']}",
        f"name: {yaml_str(flow['name'])}",
        f"version: {RESOURCE_VERSION}",
        f"summary: {yaml_str(flow['summary'])}",
        "owners:",
        f"    - {OWNER}",
        "steps:",
    ]
    total = len(flow["steps"])
    for idx, step in enumerate(flow["steps"], start=1):
        kind, title, ext_name, ext_summary = step[:4]
        note = step[4] if len(step) > 4 else None
        lines.append(f"    -   id: s{idx}")
        lines.append(f"        title: {yaml_str(title)}")
        if note:
            lines.append(f"        summary: {yaml_str(note)}")
        if kind == "externalSystem":
            lines.append("        externalSystem:")
            lines.append(f"            name: {yaml_str(ext_name)}")
            lines.append(f"            summary: {yaml_str(ext_summary)}")
        elif kind == "service":
            lines.append("        service:")
            lines.append(f"            id: {flow['refs'][idx]['service']}")
        elif kind == "message":
            lines.append("        message:")
            lines.append(f"            id: {flow['refs'][idx]['message']}")
        else:  # pragma: no cover - data error, caught by --selftest
            raise SystemExit(f"unknown step kind {kind!r} in flow {flow['id']}")
        if idx < total:
            lines.append("        next_step:")
            lines.append(f"            id: s{idx + 1}")
    lines += ["---"]
    return "\n".join(lines) + "\n\n# " + flow["name"] + "\n" + flow["body"]


def render_adr(adr):
    lines = [
        "---",
        f"id: {adr['id']}",
        f"name: {yaml_str(adr['name'])}",
        f"summary: {yaml_str(adr['summary'])}",
        f"version: {RESOURCE_VERSION}",
        f"status: {adr['status']}",
        f"date: {adr['date']}",
        "owners:",
        f"    - {OWNER}",
        "appliesTo:",
    ]
    for sid in adr["applies_to"]:
        lines.append("  - type: service")
        lines.append(f"    id: {sid}")
    lines += ["---"]
    return "\n".join(lines) + "\n" + adr["body"]


def expected_files():
    """Relative path -> rendered content. Single source of truth for the tree."""
    tree = {
        "users/lars.mdx": render_user(),
        "domains/telephony/index.mdx": render_domain(),
    }
    for svc in SERVICES:
        tree[f"services/{svc['id']}/index.mdx"] = render_service(svc)
    for evt in EVENTS:
        tree[f"events/{evt['id']}/index.mdx"] = render_event(evt)
        tree[f"events/{evt['id']}/schemas/schema.json"] = render_event_schema(evt)
    for flow in FLOWS:
        tree[f"flows/{flow['id']}/index.mdx"] = render_flow(flow)
    for adr in ADRS:
        tree[f"adrs/{adr['id']}/index.mdx"] = render_adr(adr)
    return tree


def ensure_writable(outdir: Path) -> None:
    """Refuse to write into a directory that is clearly not an export tree."""
    if outdir.exists() and not outdir.is_dir():
        raise SystemExit(f"export-catalog: {outdir} exists and is not a directory")
    for name in ("flake.nix", "modules"):
        if (outdir / name).exists():
            raise SystemExit(
                f"export-catalog: refusing to write into {outdir}: it looks like the "
                "repo root (found {name}); pass a dedicated output directory, e.g. "
                "work/out/telephony/eventcatalog"
            )


def export_tree(outdir: Path) -> None:
    ensure_writable(outdir)
    for rel, text in sorted(expected_files().items()):
        target = outdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------


def frontmatter_of(text):
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    return text[4:end]


def selftest() -> None:
    tree = expected_files()
    expected = set(tree)

    # 1. Shape: only the collections the hub contract allows, no stray files.
    allowed_prefixes = ("users/", "domains/", "services/", "events/", "flows/", "adrs/")
    for rel in expected:
        assert rel.startswith(allowed_prefixes), (
            f"{rel}: collection outside the contract"
        )

    # 2. Required frontmatter per collection (hub schema v2 REQUIRED fields).
    required = {
        "users/": ("id", "name", "email"),
        "domains/": ("id", "name", "version", "summary", "owners"),
        "services/": ("id", "name", "version", "summary", "owners"),
        "events/": ("id", "name", "version", "summary", "owners", "producers"),
        "flows/": ("id", "name", "version", "summary", "owners", "steps"),
        "adrs/": (
            "id",
            "name",
            "version",
            "status",
            "date",
            "summary",
            "owners",
            "appliesTo",
        ),
    }
    for rel, text in tree.items():
        if not rel.endswith(".mdx"):
            continue  # schemas/*.json carry no frontmatter
        fm = frontmatter_of(text)
        assert fm is not None, f"{rel}: no frontmatter"
        keys = [
            line.split(":", 1)[0]
            for line in fm.split("\n")
            if line and not line[0].isspace()
        ]
        for prefix, fields in required.items():
            if not rel.startswith(prefix):
                continue
            for field in fields:
                assert field in keys, (
                    f"{rel}: missing required frontmatter key {field!r}"
                )

    # 3. Summary/owner presence (the two per-source lint ERROR rules).
    for rel, text in tree.items():
        if rel.startswith("users/") or not rel.endswith(".mdx"):
            continue
        fm = frontmatter_of(text)
        assert fm is not None, f"{rel}: no frontmatter"
        assert "summary:" in fm, f"{rel}: summary-required"
        assert f"    - {OWNER}" in fm, f"{rel}: owner-required"

    # 4. schemaPath resolves inside the tree (refs/file-exists ERROR rule).
    for rel, text in tree.items():
        fm = frontmatter_of(text) or ""
        for line in fm.split("\n"):
            if not line.startswith("schemaPath: "):
                continue
            target = rel.rsplit("/", 1)[0] + "/" + line.split(": ", 1)[1]
            assert target in tree, f"{rel}: schemaPath {target!r} not emitted"
            json.loads(tree[target])  # must be valid JSON Schema

    # 5. Every ref resolves INSIDE this tree (per-source lint runs isolated).
    local_ids = {Path(rel).parts[1] for rel in expected if rel.count("/") > 1}
    local_ids |= {evt["id"] for evt in EVENTS}
    for rel, text in tree.items():
        fm = frontmatter_of(text) or ""
        refs = re.findall(r"^\s+(?:-\s+)?id: (\S+)$", fm, flags=re.MULTILINE)
        for rid in refs:
            if rid == DOMAIN["id"]:
                continue  # the domain's own services list, checked below
            if re.fullmatch(r"s\d+", rid):
                continue  # flow step identifiers are local anchors, not resources
            assert rid in local_ids, f"{rel}: ref {rid!r} does not resolve in this tree"

    # 6. Domain membership names services this tree emits.
    service_ids = {svc["id"] for svc in SERVICES}
    assert set(DOMAIN["services"]) <= service_ids, (
        "domain lists a service this tree lacks"
    )

    # 7. Determinism: two renders byte-identical.
    again = expected_files()
    assert again == tree, "render is not deterministic"

    # 8. Export is idempotent on disk (write twice, compare bytes).
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "eventcatalog"
        export_tree(out)
        first = {
            p.relative_to(out).as_posix(): p.read_bytes()
            for p in out.rglob("*")
            if p.is_file()
        }
        export_tree(out)
        second = {
            p.relative_to(out).as_posix(): p.read_bytes()
            for p in out.rglob("*")
            if p.is_file()
        }
        assert first == second, "export is not idempotent"
        assert set(first) == expected, (
            f"exported file set diverges from expected: {sorted(set(first) ^ expected)}"
        )

    # 9. --plain parity (no versioned outgoing refs exist to strip).
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "plain"
        export_tree(out)
        plain = {
            p.relative_to(out).as_posix(): p.read_text()
            for p in out.rglob("*")
            if p.is_file()
        }
        assert plain == tree, "--plain parity broken (the lint view diverged)"

    print(
        f"export-catalog selftest OK: 1 user, 1 domain, {len(SERVICES)} services, "
        f"{len(EVENTS)} events, {len(FLOWS)} flows, {len(ADRS)} ADR(s), "
        f"{len(expected)} files; deterministic, idempotent, isolated refs, "
        "--plain parity"
    )


def check_drift(outdir: Path) -> int:
    """Compare an existing tree with a fresh render; exit 1 on drift."""
    expected = expected_files()
    problems = []
    for rel, text in sorted(expected.items()):
        target = outdir / rel
        if not target.is_file():
            problems.append(f"missing: {rel}")
        elif target.read_text() != text:
            problems.append(f"stale: {rel}")
    for path in sorted(outdir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(outdir).as_posix()
            if rel not in expected:
                problems.append(f"unexpected: {rel}")
    if problems:
        for problem in problems:
            print(f"export-catalog: {problem}", file=sys.stderr)
        return 1
    print(f"export-catalog: {outdir} is byte-current ({len(expected)} files)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Export this repo's EventCatalog source tree.",
    )
    ap.add_argument("-o", "--out", type=Path, help="output tree root")
    ap.add_argument(
        "--plain",
        action="store_true",
        help="lint-tree parity flag (no versioned outgoing refs to strip)",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="verify an existing -o tree is byte-current instead of writing it",
    )
    ap.add_argument("--selftest", action="store_true", help="run the golden test")
    args = ap.parse_args()

    if args.selftest:
        selftest()
        return 0
    if args.out is None:
        ap.error("either -o/--out or --selftest is required")
    if args.check:
        return check_drift(args.out)
    export_tree(args.out)
    print(f"export-catalog: wrote {len(expected_files())} files to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
