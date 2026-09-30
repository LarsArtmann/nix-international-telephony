# CI posture on main — decision packet for the owner

The branch is unprotected (branch-protection API answers 404,
checked 2026-09-29), the 2026-09-24/25 red streak sat unnoticed ~26 h,
and both post-relock runner-cancels also went unnoticed. This page is
the ready-to-apply fix; everything below needs the OWNER's GitHub admin
call because **protection also blocks the auto-commit daemon's pushes
while red** — a workflow-semantics change, not a config edit.

## Current state (2026-09-30)

- CI = one workflow (`.github/workflows/ci.yml`) running
  `nix flake check` on `ubuntu-latest` (x86_64, KVM via udev rule) plus
  an `aarch64` runner, and a manual-dispatch browser E2E job.
- Known noise class: x86 infra-kills (run cancelled mid-eval, no failed
  step, aarch64 green — the 2026-09-30 ledger; protocol capped at 3
  reruns, beyond that it is a support lane). A verdict is only airtight
  via `gh run view <id> --json headSha,status,conclusion,event,jobs`.
- The README CI badge is the only always-on failure surface today.

## Option A — required checks (recommended once infra-kills are resolved)

```console
gh api -X PUT repos/LarsArtmann/nix-international-telephony/branches/main/protection \
  -H "Accept: application/vnd.github+json" \
  -F 'required_status_checks[strict]=false' \
  -F 'required_status_checks[contexts][]=nix flake check (eval, packages, VM test)' \
  -F 'required_status_checks[contexts][]=aarch64 VM test (telephony-boot, TCG)' \
  -F 'enforce_admins=false' \
  -F 'required_pull_request_reviews=null' -F 'restrictions=null' \
  -F 'allow_force_pushes=false' -F 'allow_deletions=false'
```

- `strict=false`: pushes are checked but not blocked by out-of-date
  branches (this repo pushes straight to main; no PR queue).
- `enforce_admins=false`: the owner keeps an escape hatch; the daemon's
  PAT push still gets blocked while red, which is the point.
- **Do not enable while the x86 infra-kill streak is live** — a killed
  run never completes its checks and would wedge every push for hours.
  The aarch64 job alone as required context is the safe interim:

```console
  -F 'required_status_checks[contexts][]=aarch64 VM test (telephony-boot, TCG)'
```

## Option B — minimum: failure notification (no protection)

- Owner GitHub settings → Notifications → Actions → "Send me: Only
  notify for failed workflows" for this repo (personal setting, cannot
  be scripted with the repo token).
- Optional: a `failure()`-conditioned job step in `ci.yml` posting to
  the same webhook the `alerts.urlFile` telephony units use — say the
  word and it lands as a two-line workflow edit.

## What the agent lane already shipped (2026-09-30)

- README CI badge (pre-existing, verified present).
- This decision packet; nothing here is applied — applying is F28
  (owner sign-off first).
