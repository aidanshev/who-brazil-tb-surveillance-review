# Open WHO–Brazil MDR/RR-TB Surveillance Review Platform

An open-source, bilingual (English/Portuguese), analyst-in-the-loop platform for structured review of MDR/RR-TB surveillance signals.

The platform has two layers:

1. **WHO global triage:** transparent country report cards that distinguish routine monitoring, incomplete reporting, restored reporting discontinuity, diagnostic expansion, possible epidemiologic increase, modeled-estimate discordance, persistent high burden, and low-information settings.
2. **Brazil subnational review:** a reusable country-adapter pipeline that imports raw public SINAN tuberculosis records, validates and standardizes them, aggregates by health region and quarter, compares machine learning with conventional controls, creates data-quality and epidemiologic review signals, records analyst decisions, and freezes prospective releases before later outcomes are visible.

Brazil is the complete reference implementation. A dynamic country-adapter loader, generic `run-country` command, and scaffold generator make the same architecture executable for another country without changing the common pipeline.

## Intended use

A trained TB surveillance analyst may use the platform to prioritize and structure review of testing, reporting, laboratory, and resistance patterns.

The platform **must not**:

- declare an outbreak autonomously;
- diagnose or treat an individual patient;
- treat missing data as evidence of low burden;
- rank jurisdictions punitively; or
- remove resources because a region was not selected.

## What is complete

- Raw public-data acquisition adapters for national SINAN through PySUS and a public state CSV mode.
- Immutable raw-file hashes and source manifests.
- Official SINAN field/code mapping for rapid molecular testing and drug-susceptibility testing.
- Municipality-to-health-region crosswalk workflow using `geobr`/DataSUS health regions.
- Quarterly health-region aggregation.
- Data-quality grading and fail-closed signal suppression.
- Separate reporting, testing-capacity, diagnostic-expansion, and epidemiologic-review signals.
- LightGBM challenger models for testing and RR/MDR-positive counts.
- Persistence, seasonal naïve, rolling mean, EWMA, Poisson regression, Shewhart, CUSUM, and Poisson-control comparators.
- Automatic time-holdout champion selection; AI is not forced into production when simpler models perform better.
- Bilingual FastAPI web application and JSON API.
- Persistent SQLite analyst decisions and audit logs.
- Immutable prospective release manifests with SHA-256 verification.
- WHO report-card builder and current derived report cards.
- Deterministic offline demonstration and automated tests.
- Docker and local installation paths.

## Evidence modes

### Production public-data mode

Downloads or imports official public data, records provenance, and produces candidate surveillance review signals.

### Demonstration mode

Uses a deterministic synthetic fixture with authentic SINAN column names and code conventions. This mode only verifies software behavior. The application displays a warning and its outputs must not be used for epidemiologic inference.

## Quick start: verified offline demonstration

```bash
python -m pip install -e ".[dev]"
make demo
make test
PYTHONPATH=src python -m mdrtb_surveillance.cli serve --project-root .
```

Open `http://127.0.0.1:8000`.

The demonstration produces examples of:

- reporting restoration;
- testing-capacity decline;
- diagnostic expansion;
- an epidemiologic review signal;
- small-denominator abstention; and
- automatic selection of simpler models when they outperform LightGBM.

## Full Brazil public-data rebuild

### 1. Install the Brazil dependencies

```bash
python -m pip install -e ".[brazil,dev]"
```

### 2. Build the official health-region crosswalk

```bash
Rscript scripts/build_health_region_crosswalk.R data/raw/brazil_health_region_crosswalk.csv 2024
```

The crosswalk uses the `geobr::read_health_region()` DataSUS health-region dataset and converts municipality codes to the six-digit form used by SINAN.

### 3. Download and rebuild from public SINAN data

```bash
PYTHONPATH=src python -m mdrtb_surveillance.cli run-brazil \
  --project-root . \
  --release-id brazil-public-2024-final \
  --data-vintage SINAN-final-through-2024
```

Configuration is in `configs/brazil.yaml`. The default national mode calls current PySUS `sinan(disease="TUBE", year=[...])` and stores immutable local copies.

A simpler state-level raw-public-data example is configured for the Minas Gerais open-data CSV. Set `source_mode: state_public_csv` in `configs/brazil.yaml` to use it.

### 4. Inspect the run before freezing

Each run is stored in `artifacts/runs/<release-id>/`:

- `source_manifest.json`
- `standardized_records.parquet` or `.csv.gz`
- `data_quality_periods.csv`
- `predictions.csv`
- `model_metrics.csv`
- `detector_comparison.csv`
- `alerts.csv`
- `run_summary.json`

### 5. Freeze prospectively

```bash
PYTHONPATH=src python -m mdrtb_surveillance.cli freeze \
  --project-root . \
  --release-id brazil-public-2024-final \
  --data-vintage SINAN-final-through-2024
```

The command refuses to overwrite an existing release. It copies prespecified outputs, hashes code/config/data/products, creates `manifest.json` and `LOCKED`, and makes the release directory read-only.

### 6. Verify the lock

```bash
PYTHONPATH=src python -m mdrtb_surveillance.cli verify-freeze \
  --project-root . \
  --release-id brazil-public-2024-final
```

## Analyst workflow

1. Open the alert queue.
2. Check the data-quality grade and reason code.
3. Review observed versus expected testing, RR/MDR-positive results, and resistance yield.
4. Read alternative explanations and the recommended investigation.
5. Record a blinded disposition, confidence, action, and notes.
6. Export adjudications for prospective PPV, lead-time, and investigation-yield analyses.

Permitted dispositions include:

- confirmed or probable epidemiologic increase;
- diagnostic expansion;
- reporting artifact;
- laboratory/testing interruption;
- referral change;
- random variation; and
- insufficient evidence.

## Web and API

Browser pages:

- `/`
- `/alerts`
- `/who`
- `/data-quality`
- `/models`
- `/reviews`
- `/releases`
- `/research`

JSON endpoints:

- `/api/v1/alerts`
- `/api/v1/who/report-cards`
- `/api/v1/regions/{region_id}/alerts`
- `/api/v1/releases`

## Rebuild the WHO layer

```bash
python -m pip install -e ".[who]"
PYTHONPATH=src python -m mdrtb_surveillance.cli run-who \
  --project-root . \
  --who-repo /path/to/official/gtbreport-repository
```

## Add another country

Generate a fail-closed adapter and configuration scaffold:

```bash
PYTHONPATH=src python -m mdrtb_surveillance.cli scaffold-country \
  --project-root . --country-code PER --module-name peru --class-name PeruAdapter
```

Run the completed adapter through the common pipeline with:

```bash
PYTHONPATH=src python -m mdrtb_surveillance.cli run-country \
  --project-root . --config-name peru \
  --release-id peru-public-YYYYMM --data-vintage SOURCE-VINTAGE
```

Then follow [`docs/ADDING_A_COUNTRY.md`](docs/ADDING_A_COUNTRY.md). Implement `CountryAdapter.acquire`, `standardize`, `aggregate`, and `source_description`; provide an official geography mapping and coding tests; then reuse the common data-quality, model-benchmark, alert, review, API, and release-freeze layers.

## Scientific boundary

The software can demonstrate reproducible surveillance prioritization and can prospectively measure prediction and analyst-review performance. Public aggregate data alone cannot establish that deployment improves treatment initiation, mortality, transmission, or incidence. Those claims require programme-linked outcomes and a controlled implementation study.

## License

Apache-2.0. Source data retain their original licenses and attribution requirements.

## Included verified release

The repository ships with a deterministic demonstration release (`brazil-demo-2024q4`) whose immutable freeze manifest verifies successfully. It also includes a standalone browser preview at `preview/index.html`. Demonstration outputs are clearly marked and are not epidemiologic evidence.
