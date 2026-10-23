# RoleVault — Role-Isolated Memory Governance

RoleVault is a reference implementation for conservative memory admission, temporal conflict handling, provenance-aware decisions, sensitive-data rejection, and auditable forgetting.

## Included

- src/rolevault/: core V2.7-Fusion reference implementation.
- tests/: focused unit and regression tests for the core memory-governance logic.
- app/decision-lab.html and app/lab/: a static, deterministic decision-lab demo using synthetic scenarios only.

## Quick start

Python 3.10+; core implementation uses the Python standard library.

    $env:PYTHONPATH = "src"
    python -m unittest discover -s tests -v

To view the synthetic decision lab:

    python -m http.server 8000 --directory app

Open http://127.0.0.1:8000/decision-lab.html.

## Security and evidence boundaries

- The demo uses synthetic scenarios; it does not call a live model or authenticate a real TeleAgent account.
- This repository intentionally excludes USER.md, personal memory files, native conversation logs, real snapshots, local app/data.json, evidence bundles, PDFs, videos, and credentials.
- Trusted identity must be supplied by a separately authenticated host; a role label inside chat text is not authentication.
- A local reference implementation does not prove account-global isolation, external cache erasure, or platform-native integration.
- The R04 transcription/hash exception from the private evaluation workspace is not part of the public product code and is not silently represented as a pass.
