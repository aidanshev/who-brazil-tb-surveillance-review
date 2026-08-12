# Publication readiness

## Current release class

`SOURCE_RICH_PLATFORM_PAYLOAD`

This repository contains the materialized core surveillance-review modules (`alerts`, `benchmark`, `cli`, `config`, `models`, `pipeline`, and `who`), the upstream platform README retained as documentation, aggregate decision-analysis results, source/provenance records, and public-release safety tooling.

## Reproducibility boundary

This is a publication-focused source-rich extraction of the platform, not a byte-for-byte mirror of the complete upstream working directory. Additional upstream modules, configuration, tests, deployment assets, or web components may exist outside this public tree. The manuscript's decision analysis is a secondary synthesis of the WHO and Brazil model outputs and must not be presented as a third independent predictive validation study.

## Publication safeguards

- The repository keeps governance/actionability claims separate from outbreak or causal claims.
- Scenario PPV is labeled as assumption-dependent rather than empirical program performance.
- Raw surveillance records and third-party image binaries are excluded.
- `tools/public_release_audit.py` and GitHub Actions enforce the public-tree safety policy.
- `CITATION.cff` does not claim a release version or DOI before a real immutable release exists.

## Items remaining before permanent archival release

1. Reconcile the publication-focused tree against the authoritative upstream platform and either materialize all code required for the manuscript analyses or document every intentionally omitted component.
2. Select an explicit software license after ownership/upstream-license review.
3. Cross-reference the primary WHO-global and Brazil forecasting repositories in the manuscript/code-availability statement to avoid implying independent evidence.
4. Create an immutable release and preservation DOI after the final reconciliation and add that DOI to repository and manuscript citation metadata.
