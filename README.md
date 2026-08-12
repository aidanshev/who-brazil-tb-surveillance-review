# WHO-Brazil Tiered TB Surveillance Review

**Repository status:** `SOURCE_RICH_PLATFORM_PAYLOAD`

Human-in-the-loop surveillance review and decision-analysis framework combining WHO global and Brazil subnational evidence.

## Public-release policy

This repository is code/provenance-forward: raw patient-level surveillance data are excluded, third-party datasets are linked rather than mirrored, and image binaries are intentionally excluded. Source sites for visuals and data are recorded in `FIGURE_AND_IMAGE_PROVENANCE.md` and `DATA_SOURCES.md`.

Run before publishing:

```bash
python tools/public_release_audit.py
```

## Layout

- `src/`: materialized core surveillance-review modules
- `results/`: publication-safe aggregate decision-analysis results
- `docs/`: upstream/platform and publication documentation
- `REPOSITORY_STATUS.md`: completeness status

## Publication documentation

- `PUBLICATION_READINESS.md`: exact platform/reproducibility boundary
- `CODE_AVAILABILITY.md`: evidence-matched manuscript Code Availability language
- `RELEASE_CHECKLIST.md`: completed and remaining archival steps
- `docs/UPSTREAM_PLATFORM_README.md`: retained upstream platform documentation
- `CITATION.cff`: repository citation metadata

## Archival DOI

Before permanent archival, reconcile this publication-focused tree against the authoritative upstream platform and document any intentional omissions. Then create an immutable GitHub Release, archive it with Zenodo or an equivalent preservation service, and add the DOI to this README, `CITATION.cff`, and the manuscript. Primary predictive evidence should be cross-cited to the WHO-global and Brazil forecasting repositories rather than treated as independent validation.
