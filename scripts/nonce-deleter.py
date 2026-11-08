#!/usr/bin/env python3
"""One-shot nonce-store deleter: reproduce the sofia digest-auth race.

Runs INSIDE the VM (push it in with the interactive test driver, e.g.
`machine.copy_from_host` / a `machine.succeed("python3 /tmp/nonce-deleter.py")`,
or wire it via environment.etc in a suite). Deletes ONE fresh nonce row
(newest first) from mod_sofia's sip_authentication sqlite store in the
window between the 407 challenge and the authorized re-INVITE.

Expected signatures (the 2026-10-26 A/B):
  - one-round client:  rc=2, INVITE answered 407 forever (CI red shape)
  - re-challenging client (tests/sip.py call(), 3 rounds): the stale=true
    re-challenge's own nonce row exists, so the next round converges
    and the call proceeds (rc=0).

RECONSTRUCTED 2026-11-07 from the archived 2026-10-26 session report
(docs/status/archived/2026-10-26_07-01_...ci-recovery.md §d/§e) — the
original /tmp harness died with the session. The report's two
false-start bug classes (a mangled shell guard `${$n:-0}` and a wrong
`-ge 3` threshold, each costing a full VM boot cycle) are recorded in
docs/lessons/vm-testing.md; this python version sidesteps that class
by taking the row count as argv and refusing to run unbounded.
"""

import sqlite3
import sys

DB_CANDIDATES = (
    "/var/lib/freeswitch/db/core",
    "/var/lib/freeswitch/db/internal",
    "/var/lib/freeswitch/db/external",
)


def find_nonce_db() -> str:
    for path in DB_CANDIDATES:
        try:
            conn = sqlite3.connect(path)
            has_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table'"
                " AND name='sip_authentication'"
            ).fetchone()
            conn.close()
            if has_table:
                return path
        except sqlite3.Error:
            continue
    raise SystemExit(
        "no sip_authentication store found under "
        + ", ".join(DB_CANDIDATES)
        + " — check the sofia profile's dsn"
    )


def main() -> None:
    count = 1
    if len(sys.argv) > 1:
        count = int(sys.argv[1])
    if count < 1 or count > 3:
        raise SystemExit("refusing unbounded deletes: pass 1..3 rows")

    db = find_nonce_db()
    conn = sqlite3.connect(db)
    newest = conn.execute(
        "SELECT nonce FROM sip_authentication ORDER BY rowid DESC LIMIT ?",
        (count,),
    ).fetchall()
    if not newest:
        print(f"{db}: nonce store empty — nothing to delete")
        return
    placeholders = ",".join("?" for _ in newest)
    cur = conn.execute(
        f"DELETE FROM sip_authentication WHERE nonce IN ({placeholders})",
        [row[0] for row in newest],
    )
    conn.commit()
    conn.close()
    print(
        f"{db}: deleted {cur.rowcount} nonce row(s) "
        f"({len(newest)} targeted, newest first)"
    )


if __name__ == "__main__":
    main()
