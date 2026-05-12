.. _historical-process:

***********************************
Historical CSV → CDF Processing CLI
***********************************

The ``process`` subcommand of ``python -m swxsoc_reach`` promotes
historical data products one level at a time:

- ``--target-level l1c`` (default) — convert per-day UDL CSV files
  produced by :ref:`historical-download` into L1C CDFs.
- ``--target-level l2`` — promote existing L1C CDFs into L2
  products (typically multiple CDFs + ancillary JPGs per day).
- Higher levels (``l3``, ...) are accepted by the CLI when present in
  ``swxsoc.config["mission"]["valid_data_levels"]`` but their
  producers may not be wired up yet; days at unimplemented levels
  surface as ``SKIPPED_NO_INPUT`` or ``FAILED`` per-day rows rather
  than an upfront error.

S3 upload is opt-in and applies to every produced output (CDFs and
JPGs alike). The orchestrator is sequential at the day level and
resumable: rerunning the same date range only re-attempts days that
are not already complete at the chosen ``--target-level`` according
to the shared telemetry CSV.

This is Phase 2 of the historical reprocessing toolchain. Phase 1
(download) is documented at :ref:`historical-download`.

Quick start
===========

.. code-block:: shell

    # Phase 1: download the day's CSV
    python -m swxsoc_reach download \
        --start-date 2026-01-01 --end-date 2026-01-01 \
        --sensor-id REACH-1 --output-dir ./out

    # Phase 2 — produce an L1C CDF (default --target-level)
    python -m swxsoc_reach process \
        --start-date 2026-01-01 --end-date 2026-01-01 \
        --sensor-id REACH-1 \
        --input-dir ./out --output-dir ./out_cdf

    # Phase 2 — promote the L1C CDF to L2 (reads prior L1C row
    # from the shared telemetry CSV; no CSV glob needed)
    python -m swxsoc_reach process \
        --start-date 2026-01-01 --end-date 2026-01-01 \
        --sensor-id REACH-1 \
        --input-dir ./out --output-dir ./out_cdf \
        --target-level l2

    # Phase 2 (with S3 upload) at L1C
    python -m swxsoc_reach process \
        --start-date 2026-01-01 --end-date 2026-01-01 \
        --sensor-id REACH-1 \
        --input-dir ./out --output-dir ./out_cdf \
        --upload-to-s3 --s3-bucket dev-swxsoc-pipeline-incoming

CLI reference
=============

Required arguments
------------------

- ``--start-date YYYY-MM-DD`` — inclusive UTC start date.
- ``--end-date YYYY-MM-DD`` — inclusive UTC end date.
- ``--input-dir PATH`` — directory holding Phase 1 download
  artifacts. Used only when ``--target-level l1c`` (the default).
  For higher levels the input is auto-resolved from the telemetry
  CSV (see :ref:`process-input-resolution`).
- ``--output-dir PATH`` — directory where CDF / JPG outputs are
  written.

Optional arguments
------------------

- ``--telemetry-file PATH`` — append-only telemetry CSV. Defaults to
  ``<input-dir>/download_telemetry.csv`` (the same file Phase 1
  writes). Use this only if you keep telemetry separate from the
  download artifacts.
- ``--sensor-id`` — REACH sensor identifier or ``ALL`` (default).
  Drives the L1C input filename pattern.
- ``--descriptor`` — UDL descriptor (default ``QUICKLOOK``).
- ``--output-format`` — input serialization format (default ``csv``).
- ``--target-level`` — output data level to produce. Choices are
  derived from ``swxsoc.config["mission"]["valid_data_levels"]``
  (currently ``raw``, ``l1c``, ``l2``, ``l3``); default ``l1c``.
  Anything other than ``l1c`` must be passed explicitly. The CLI
  does not pre-validate that a producer is implemented for the
  chosen level — unimplemented levels surface as per-day
  ``SKIPPED_NO_INPUT`` (no prior-level row) or ``FAILED`` rows.
- ``--retry-failed`` — re-attempt days whose latest telemetry row
  at the chosen level is ``FAILED``. See the two-tier semantics in
  :ref:`process-restart-semantics`.
- ``--limit-days N`` — cap attempted days, counted from the first
  day in the range that is not already complete.
- ``--dry-run`` — plan only: log per-day actions, write no
  telemetry, do no work.
- ``-v`` / ``-vv`` — increase logging verbosity.

S3 upload arguments
-------------------

- ``--upload-to-s3`` — when set, every produced output file (CDFs
  and JPGs) is uploaded via
  :func:`sdc_aws_utils.aws.push_science_file`. ``UPLOADED`` is the
  terminal status per file. Without this flag, ``PROCESSED`` is
  terminal.
- ``--s3-bucket`` — destination bucket (required iff
  ``--upload-to-s3`` is set).
- ``--aws-region`` — optional AWS region. Defaults to ``boto3``'s
  standard region resolution chain.

Optional dependencies
=====================

S3 upload requires the optional ``net`` extra:

.. code-block:: shell

    pip install 'swxsoc_reach[net]'

This installs ``boto3`` and ``sdc_aws_utils``. Without these, calling
``--upload-to-s3`` raises ``RuntimeError`` with an install hint.

.. _process-input-resolution:

Input resolution per level
==========================

- ``l1c`` — the orchestrator globs ``--input-dir`` for the per-day
  CSV named per
  :func:`~swxsoc_reach.net.udl.build_reach_output_filename`. Days
  with no match are recorded as ``SKIPPED_NO_INPUT``.
- ``l2`` — the orchestrator looks up the prior-level
  (``l1c``) row in the shared telemetry CSV for that date and
  reads the L1C ``cdf_path`` from it. If no L1C row exists for the
  date, the day is ``SKIPPED_NO_INPUT``. If multiple L1C rows
  exist (e.g. reprocessed days), the day is ``SKIPPED_NO_INPUT``
  with reason ``"ambiguous prior level rows for l2"`` and must be
  resolved manually.
- ``l3`` and above — not implemented; recorded as
  ``SKIPPED_NO_INPUT``.

Status lifecycle
================

Stage-prefixed pending statuses indicate which stage was interrupted:

- ``PROCESS_PENDING`` — ``process_file`` invocation in progress.
  Written before the call with ``cdf_path=""`` for traceability.
- ``PROCESSED`` — one row per produced output file. Terminal in
  local-only mode.
- ``UPLOAD_PENDING`` — S3 upload in progress, written per file.
- ``UPLOADED`` — file successfully uploaded. Terminal in upload
  mode.
- ``SKIPPED_NO_INPUT`` — no input artifact available for the target
  level (CSV missing for L1C, or no prior-level CDF for L2+).
  Re-runnable: the day is re-attempted if the input later appears.

A ``PROCESS_PENDING`` or ``UPLOAD_PENDING`` row with no finalized
successor (PROCESSED / UPLOADED / FAILED) sharing the same
``run_id`` is treated as an **orphan** from a crashed run and is
reprocessed / retried on the next invocation.

Phase 1 statuses (``DOWNLOAD_PENDING``, ``DOWNLOADED``,
``SKIPPED_NO_DATA``) live in the ``raw`` level and are ignored by
the process orchestrator's restart logic at higher levels.

Telemetry schema
================

The process orchestrator writes **one row per produced output file**
(L1C: 1 row/day; L2: typically ~12 rows/day for the 6 CDFs +
6 JPGs). It also writes one ``PROCESS_PENDING`` traceability row
per day (with ``cdf_path=""``) and one ``FAILED`` row per day if
``process_file`` raises.

Phase 2 extends the Phase 1 download telemetry CSV with these
columns (all default to ``""`` for older rows):

- ``data_level`` — ``raw`` (download), ``l1c``, ``l2``, ... per
  ``swxsoc.config["mission"]["valid_data_levels"]``.
- ``process_seconds`` — wall-clock seconds spent in
  :func:`process_file` for the day.
- ``cdf_size_mb`` — size of the produced output file in megabytes.
- ``cdf_path`` — local path of the produced output. Holds CDF
  paths and JPG paths alike (the column is the row's "primary
  output artifact"). Empty for ``PROCESS_PENDING`` traceability rows
  and process-stage ``FAILED`` rows.
- ``upload_seconds`` — wall-clock seconds spent in the S3 upload
  for this file.
- ``s3_bucket`` — destination bucket reported on a successful
  upload.
- ``s3_key`` — S3 key returned by
  :func:`sdc_aws_utils.aws.push_science_file`.

Row identity is ``(chunk_date_utc, data_level,
basename(cdf_path or csv_path))`` plus ``status``;
``HistoricalTelemetry.load_state()`` deduplicates by that key,
keeping the most-recent row per identity (file order breaks ties).

.. _process-restart-semantics:

Restart semantics
=================

A day ``(date, target_level)`` is **complete** when every row in
the state list has a terminal status, scoped to the requested mode:

- Local-only mode: every row is ``PROCESSED`` or ``UPLOADED``.
- Upload mode: every ``PROCESSED`` row has a matching ``UPLOADED``
  row sharing the same ``cdf_path``.

Per-day action taxonomy:

- ``skip_existing`` — day is complete at the requested level/mode.
- ``run_process`` — the day's L1C run has not happened, an orphan
  ``PROCESS_PENDING`` row is present, the prior attempt left
  process-stage ``FAILED`` rows (with ``--retry-failed``), or the
  CDF on disk is missing.
- ``run_upload_only`` — ``PROCESSED`` rows exist without matching
  ``UPLOADED`` rows; uploads requested. Orphan ``UPLOAD_PENDING``
  rows are also treated as needing upload retry.
- ``skip_failed`` — at least one ``FAILED`` row exists and
  ``--retry-failed`` was not passed.
- ``skip_no_input`` — no input artifact available (see
  :ref:`process-input-resolution`).

``--retry-failed`` has two tiers:

- If the only FAILED rows for the day at the target level are
  **upload-stage** rows (i.e. they have a populated ``cdf_path``
  whose file still exists on disk), those individual files are
  retried in place; no reprocess.
- If any **process-stage** FAILED row is present (``cdf_path=""``),
  the entire day is reprocessed at that level. All per-file rows
  from the prior attempt are superseded by the new attempt.

Operator runbook
================

Process succeeded but one upload failed
   The day's row sequence at the target level ends in
   ``UPLOAD_PENDING`` then ``FAILED`` for the affected file; sibling
   files for the same day may already be ``UPLOADED``. The CDF / JPG
   is on disk in ``--output-dir``. Resolve the cause (creds, bucket
   access, etc.), then rerun with ``--retry-failed``: only the
   FAILED upload rows are retried; the already-uploaded files are
   untouched.

Process failed mid-day
   The day's row sequence at the target level ends in
   ``PROCESS_PENDING`` then a process-stage ``FAILED``
   (``cdf_path=""``). Inspect ``error_type`` / ``error_message``,
   fix the underlying issue, then rerun with ``--retry-failed``;
   the orchestrator reprocesses the entire day at that level.

CDF or JPG accidentally deleted
   Delete any of the day's outputs and rerun without
   ``--retry-failed``. The orchestrator detects the missing file
   (the day no longer looks "complete") and reprocesses the day at
   the target level — including all sibling outputs at L2.

Promoting an existing L1C day to L2
   Once Phase 2 at ``--target-level l1c`` has populated the
   telemetry CSV with an L1C ``PROCESSED`` row for the date, simply
   rerun with ``--target-level l2``:

   .. code-block:: shell

       python -m swxsoc_reach process \
           --start-date 2026-01-01 --end-date 2026-01-01 \
           --sensor-id REACH-1 \
           --input-dir ./out --output-dir ./out_cdf \
           --target-level l2

   The orchestrator reads the L1C ``cdf_path`` from telemetry,
   feeds it to ``process_file``, and emits one ``PROCESSED`` row
   per produced output (CDFs + JPGs).

Legacy compatibility
====================

Rows pre-dating this change have no ``data_level`` column. They
are interpreted at read time:

- A row with a non-empty ``csv_path`` synthesizes a ``raw`` row.
- A row with a non-empty ``cdf_path`` synthesizes an ``l1c`` row.

The on-disk CSV is rewritten in place to the new schema on the
next ``append_row`` call, but the synthesized levels remain
correct either way. ``--target-level l1c`` reruns over legacy
telemetry continue to skip completed days correctly without
operator intervention.

Notes & caveats
===============

- ``process_file`` writes to ``Path.cwd()`` when
  ``LAMBDA_ENVIRONMENT`` is unset, which is always the case for a
  historical local run. The orchestrator chdir's into
  ``--output-dir`` for the duration of each call and restores the
  prior cwd in ``finally``. This is unchanged by the multi-level
  work.
- When the same telemetry CSV is shared with Phase 1 (recommended),
  rerunning the ``download`` subcommand after ``process`` continues
  to behave correctly: the downloader consults
  ``HistoricalTelemetry.load_download_state()``, which filters to
  the ``raw`` level only.
- The ``cdf_path`` column intentionally also holds JPG paths at
  L2 (it is semantically the row's primary output artifact). It is
  not renamed to avoid breaking legacy CSV reads.
