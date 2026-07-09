# swxsoc_reach — Agent Guide

`swxsoc_reach` is a NASA SWxSOC Python package that gets, processes, and analyzes data
from the **REACH** (Responsive Environmental Assessment Commercially Hosted) dosimeter
constellation — 32 payloads / 64 dosimeters flown on Iridium NEXT. It is a mission
package built on top of the shared [`swxsoc`](https://github.com/swxsoc/swxsoc) framework
(pulled as a git dependency) and follows the SunPy/Astropy-style layout used across SWxSOC
mission packages.

For deeper background see the docs (built with Sphinx, published on ReadTheDocs):
- [docs/user-guide/](docs/user-guide/index.rst) — overview, constellation, data objects, geomaps, historical CLI, customization, logging
- [docs/dev-guide/](docs/dev-guide/index.rst) — coding standards, dev env, tests, docs, maintainer workflow
- [README.rst](README.rst) — mission summary and data availability

## About the REACH Mission

REACH is a U.S. Space Force / Aerospace Corporation program of 32 hosted payloads
("pods") flying on the commercial Iridium NEXT low-Earth-orbit constellation (~800 km).
Each pod carries two dosimeters (built by Aerospace, manufactured by Teledyne), and across
the fleet six sensor "flavors" — distinguished by detector design and shielding — set
different electron/proton energy thresholds, letting REACH map space-weather hazards (e.g.,
internal charging in the outer belt, single-event effects in the inner proton belt and over
the polar caps) with dense, global, low-latency coverage. Aerospace pushes the source data
to the Unified Data Library (UDL), which this package ingests and processes.

## Golden Rules

- **Delegate to `swxsoc`, don't reinvent.** All CDF I/O, time handling, coordinate frames,
  filename parsing, and the config/logging system come from `swxsoc`. REACH classes
  *subclass* `swxsoc.swxdata.SWXData` (see `REACHTrack`, `GenericGeoMap`) rather than
  re-implementing containers. When iterating on `swxsoc` behavior locally, prefer an
  editable install (`pip install -e ../../SpaceWeatherSOC/swxsoc`) over version bumps.
- **Match the file you're editing.** These docstrings are NumPy-style and many functions
  ship doctests. Preserve existing style; don't reformat unrelated code.
- **Surgical edits over reformat-the-world.** This repo has active PRs and a Lambda
  processing path that depends on stable public function signatures.

## Build, Test, Lint, Docs

Run everything from this package root (`/swxsoc_reach/`), inside a dedicated env
(`conda create -n reach python=3.12 && conda activate reach`).

```bash
pip install -e ".[dev]"                 # docs + test + style + net + pre-commit extras
pytest                                  # testpaths = swxsoc_reach/tests + docs/ (doctests + RST)
pytest swxsoc_reach/tests/test_udl.py   # run one module
ruff check --fix && ruff format         # authoritative lint/format (line-length 88, py310)
pre-commit run --all-files              # ruff + hygiene hooks
cd docs && make html                    # Sphinx build (sphinx-automodapi, pydata theme)
```

- **Python floor is 3.10** (`requires-python = ">=3.10"`, ruff `target-version = "py310"`).
  CI ([.github/workflows/testing.yml](.github/workflows/testing.yml)) runs the matrix on
  3.10–3.13 across Linux/macOS/Windows, so don't use syntax that breaks 3.10 or is
  OS-specific. (The `classifiers` list under-advertises this; trust `requires-python`.)
- **`ruff` is the source of truth** for style — enforced by
  [.pre-commit-config.yaml](.pre-commit-config.yaml) and
  [.github/workflows/codestyle.yml](.github/workflows/codestyle.yml). The legacy
  [.devcontainer/devcontainer.json](.devcontainer/devcontainer.json) still points VS Code
  at black/pylint; **ignore that** and use ruff.
- **Doctests count.** Examples in docstrings and `docs/**/*.rst` are collected by
  `pytest-doctestplus` (`addopts = --doctest-rst --doctest-plus`). Keep examples runnable.
- **Version is generated** by `setuptools_scm` into
  [swxsoc_reach/_version.py](swxsoc_reach/_version.py) — never hand-edit it.
- Store new test fixtures under `swxsoc_reach/data/test/` and keep them small (<~100 kB).

## Architecture

Everything hangs off `swxsoc`'s `SWXData` container. The two REACH subclasses are the
backbone of the science pipeline:

- **`REACHTrack`** ([swxsoc_reach/track/trackbase.py](swxsoc_reach/track/trackbase.py)) —
  in-memory wrapper over an L1C CDF; per-sensor geolocation + dose-rate time series.
- **`GenericGeoMap`** ([swxsoc_reach/geomap/geomapbase.py](swxsoc_reach/geomap/geomapbase.py)) —
  gridded (lon × lat × flavor) dose-rate map with per-statistic slices; the L2 product.

### Data pipeline (three phases)

```
UDL (Unified Data Library)  ── net/udl.py, net/auth.py ──►  per-day JSON/CSV
        │  (historical/ orchestrates multi-day, telemetry-tracked, resumable)
        ▼
io/file_tools.read_file()  ──►  pandas DataFrame
        ▼
calibration/transform.build_swxdata()   (dedup → impute sensor IDs → sparse
        │                                 time×sensor×flavor arrays + geolocation)
        ▼
SWXData.save()  ──►  L1C CDF          (calibration/calibration.process_file entry point)
        ▼
REACHTrack.load(L1C).to_geomap()   (scipy.stats.binned_statistic_2d per flavor,
        │                            7 statistics: sum/mean/median/count/min/max/std)
        ▼
GenericGeoMap.save()  ──►  L2 gridded CDF  +  per-flavor PNG (visualization/viz.plot_geomap)
```

`calibration.process_file()` is the single entry point used by both the historical CLI and
the SWxSOC Lambda processor: given a UDL file it produces an L1C CDF; given an L1C CDF it
produces the L2 geomap CDF + PNGs.

### Subpackage map

| Subpackage | Responsibility | Key symbols |
|---|---|---|
| [calibration/](swxsoc_reach/calibration/) | UDL→`SWXData`→CDF transform; L1C→L2 geomap+PNG | `process_file()`, `build_swxdata()`, `deduplicate_records()` |
| [io/](swxsoc_reach/io/) | File dispatch (UDL JSON/CSV/CDF) → DataFrame/`SWXData` | `read_file()`, `read_udl_json()`, `read_udl_csv()` |
| [net/](swxsoc_reach/net/) | UDL HTTP query, auth, AIMD rate limiting | `download_UDL_reach_window()`, `resolve_udl_auth()`, `AdaptiveRateController` |
| [historical/](swxsoc_reach/historical/) | Multi-day orchestration, telemetry, S3 upload | `run_download()`, `run_process()`, `HistoricalTelemetry`, `upload_cdf_to_s3()` |
| [track/](swxsoc_reach/track/) | L1C CDF wrapper; per-sensor extraction, geomapping | `REACHTrack.get_track()/.to_geomap()/.truncate()/.plot()` |
| [geomap/](swxsoc_reach/geomap/) | L2 gridded map storage + plotting | `GenericGeoMap.map_data()/.lon_lat_grid()/.plot()` |
| [visualization/](swxsoc_reach/visualization/) | Cartopy region maps, geomaps, dose plots | `plot_geomap()`, `plot_regions()`, `plot_region_contours()` |
| [util/](swxsoc_reach/util/) | Enums, CDF schema, geometry, filename helpers | `Region`, `Flavor`, `SensorId`, `REACHDataSchema`, `create_reach_filename()` |
| [data/](swxsoc_reach/data/) | Mission config, CDF attr schemas (YAML), region contours (NPZ) | `reach_id_dosimeter_relationship.json`, `region_contour_paths.npz` |
| [tests/](swxsoc_reach/tests/) | Unit + integration (pipeline, CLI, orchestrators) | `test_calibration.py`, `test_cli.py`, `test_udl.py` |

### Core enums — [swxsoc_reach/util/enums.py](swxsoc_reach/util/enums.py)

These model the constellation and are used everywhere; learn them before touching the
pipeline:

- **`SensorId`** (`Flag`) — the 32 payloads `REACH-101`…`REACH-181`. `from_str()` parses
  `"REACH-101"` / `"reach_101"` / `"101"`; `to_index()` gives the 0–31 array position.
- **`Flavor`** (`Flag`) — dosimeter energy channels `U,V,W,X,Y,Z` (+ `ALL`); `.label` returns
  LaTeX particle strings. Each sensor carries **two** flavors.
- **`Region`** — geomagnetic zones `SAA`, `POLAR_CAP`, `OUTER_ZONE`, `SLOT` (mask index,
  code, label, color) used to tag points and color geomaps.
- **`load_reach_id_dosimeter_relationship()`** loads
  `data/reach_id_dosimeter_relationship.json` at import into the package-level
  `REACH_ID_DOSIMETER_RELATIONSHIP` (`dict[SensorId, tuple[Flavor, ...]]`); it is cached.

## The `historical` CLI

`python -m swxsoc_reach` ([swxsoc_reach/__main__.py](swxsoc_reach/__main__.py)) exposes two
idempotent, telemetry-tracked subcommands. Always treat `--help` as the source of truth for
flag values (docs and code have drifted on descriptor naming, e.g. `QUICKLOOK`/`PROVISIONAL`
vs. `prelim`).

```bash
python -m swxsoc_reach download --help   # per-day UDL download over a UTC date range
python -m swxsoc_reach process  --help   # per-day CSV → CDF (+ optional --upload-s3)
```

- Reruns skip days already terminal in the append-only telemetry CSV
  ([historical/telemetry.py](swxsoc_reach/historical/telemetry.py)); use `--retry-failed`
  / `--dry-run` when iterating.
- `sensor_id=ALL` fans out into ~288 UDL requests/day (5-min chunks); a specific sensor
  uses ~4/day (6-hour chunks). See
  [historical/download_orchestrator.py](swxsoc_reach/historical/download_orchestrator.py).

## Operational / SWxSOC integration

- **Mission env var**: [`__init__.py`](swxsoc_reach/__init__.py) sets `SWXSOC_MISSION`
  (default `swxsoc_pipeline`), which drives `swxsoc`'s config/schema resolution. Don't
  hardcode mission values that this should supply.
- **UDL credentials**: [`net/auth.resolve_udl_auth()`](swxsoc_reach/net/auth.py) resolves,
  in order, `BASICAUTH` env var → `SECRET_ARN_UDL` (AWS Secrets Manager, JSON `basicauth`
  key) → error. `boto3` is imported lazily and only needed via the `[net]` extra.
- **Lambda path**: `calibration.process_file()` detects `LAMBDA_ENVIRONMENT` and writes
  outputs to `/tmp` (Lambda's only writable dir). S3 upload
  ([historical/s3_upload.py](swxsoc_reach/historical/s3_upload.py)) stages the CDF in
  `/tmp` before calling `sdc_aws_utils.aws.push_science_file()`. The
  [calibration.yml](.github/workflows/calibration.yml) workflow builds & smoke-tests the
  SWxSOC processing Lambda against PRs — keep `process_file()`'s signature/behavior stable.
- **AWS bits are optional**: `boto3` + `sdc_aws_utils` come from the `[net]` extra; code
  degrades gracefully when they're absent.

## Pitfalls

- **Don't hand-edit** `swxsoc_reach/_version.py` (setuptools_scm) or the generated
  `docs/_autosummary/` / `docs/_build/` outputs.
- **Never strip whitespace from data fixtures.** pre-commit excludes `.json`/`.txt`/`.fits`
  from the trailing-whitespace and line-ending hooks — respect that for `data/` files.
- **Editable cross-repo installs can desync.** If an import resolves `swxsoc` (or
  `sdc_aws_utils`) from an unexpected location, check `pip show <pkg>` before debugging logic.
- **Descriptor/flavor names differ between docs and code** — verify against `--help` and the
  enums, not the prose docs.
- **Geomap/plot code deliberately suppresses `log10(0)` and Matplotlib label warnings**
  because REACH dose data legitimately contains zeros; don't "fix" those by removing the
  guards.
