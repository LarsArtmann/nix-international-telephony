# docs/research — point-in-time research reports

Deep-dive audits and provider/platform surveys. Snapshots: annotate, never
rewrite (an addendum section is the correction mechanism, per the 2026-10-01
report's own addendum precedent).

| Date | Report | Subject | Verdict / refresh trigger |
| ---- | ------ | ------- | ------------------------- |
| 2026-10-25 | [2026-10-25_webphone-deep-dive.html](2026-10-25_webphone-deep-dive.html) | webphone (2.9.0 @ 50c4ac2) full capability audit | 80/100 (high), 21/27 fully leveraged; supersedes 2026-10-01. Refresh: when the push seam or ASR facade lands, or on the next webphone release tag |
| 2026-10-07 | [2026-10-07_flake-inputs-deep-dive.html](2026-10-07_flake-inputs-deep-dive.html) | all seven flake inputs, webphone focus | webphone nix-consumption 88/100; stands for its narrower scope |
| 2026-10-01 | [2026-10-01_webphone-deep-dive.html](2026-10-01_webphone-deep-dive.html) | webphone (2.8.0 @ 4266b8d) | 78/100; SUPERSEDED by 2026-10-25 (all six findings executed same-day, addendum records verdicts) |
| 2026-09-16 | [2026-09-16_sip-ecosystem-survey.md](2026-09-16_sip-ecosystem-survey.md) | SIP ecosystem / PBX platform survey | fed the no-FusionPBX generate-XML-from-Nix decision |
| 2026-09-15 | [2026-09-15_nix-ssh-config-deep-dive.html](2026-09-15_nix-ssh-config-deep-dive.html) | nix-ssh-config input | led to adoption (`services.ssh-server`) |
