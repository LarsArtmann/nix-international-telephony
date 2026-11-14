# Draft: pma committer — configurable ExcludePathspecs (the flake.lock lever)

Status: DRAFT + verified evidence, owner applies (pma code + daemon
config + restart — a live-fleet change, not a consumer-repo change).
Prepared 2026-11-14 (SUPERB M20); all claims verified in the
projects-management-automation checkout at `4c4f4864`.

## Verified evidence

- `pma-daemon/committer/committer.go` `Config.ToCommitOptions()`
  hardcodes `ExcludePathspecs` to exactly the result/result-* nix
  symlinks pair; `Config` (line 149) has NO pathspec field — the lever
  exists in `commit.Options` (the go-commit lib) but is unreachable
  from configuration.
- `NoVerify: true` is STRUCTURAL and deliberate (the 2026-08-19
  incident comment: repo hooks need an interactive toolchain the
  service PATH lacks). Hook-side gating of daemon commits is therefore
  NOT reachable by config either — it needs the hooks-runnable-in-daemon
  lane (pma#341 covered only the dead `skip_hooks` flag; CLOSED).
- Fleet exposure (measured 2026-11-14): **218 repos** on this machine
  carry a `flake.lock` AND daemon commits within 30 days — every one is
  exposed to the daemon committing a swept/unvetted lock move (the
  nix-international-telephony incident class: unattributed relocks,
  forward-pins onto broken revs).

## Proposed change (minimal)

```go
type Config struct {
    ...
    // ExcludePathspecs appends to the hardcoded result-symlink pair
    // (never replaces it).
    ExcludePathspecs []string
}

func (c Config) ToCommitOptions() commit.Options {
    return commit.Options{
        ...
        ExcludePathspecs: append([]string{
            ":(exclude,glob)**/result",
            ":(exclude,glob)**/result-*",
        }, c.ExcludePathspecs...),
        ...
    }
}
```

Then the daemon's per-project (or global) config adds
`:(exclude,glob)flake.lock` for lock-guarded repos — lock moves become
CLI-only by construction, which is exactly what those repos'
lock-move-guard commit-msg hooks assume. Cost note: excluding flake.lock
means a daemon that LEGITIMATELY relocks (via an explicit session) no
longer auto-commits the move — the session's hand-authored commit
becomes the only path, which is the desired shape.

## Why this beats hook-side gating

Hooks cannot run in the daemon's service PATH today (NoVerify comment);
pathspec exclusion needs no toolchain, is config-only, and removes the
hazard class at the STAGING layer instead of policing it at commit time.
