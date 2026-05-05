.. _historical-process:

***********************************
Historical CSV → CDF Processing CLI
***********************************

The ``process`` subcommand of ``python -m swxsoc_reach`` converts the
per-day UDL CSV files produced by :ref:`historical-download` into
CDFs, with optional S3 upload. It is sequential at the day level and
resumable: rerunning the same date range only re-attempts days that
are not already complete according to the shared telemetry CSV.

This is Phase 2 of the historical reprocessing toolchain. Phase 1
(download) is documented at :ref:`historical-download`.

Quick start
===========

.. code-block:: shell

    # Phase 1: download the day's CSV
    python -m swxsoc_reach download \
        --start-date 2026-01-01 --end-date 2026-01-01 \
        --sensor-id REACH-1 --output-dir ./out

    # Phase 2 (local-only): produce a CDF
    python -m swxsoc_reach process \
        --start-date 2026-01-01 --end-date 2026-01-01 \
        --sensor-id REACH-1 \
        --input-dir ./out --output-dir ./out_cdf

    # Phase 2 (with S3 upload): also upload to S3
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
  artifacts. The orchestrator globs this directory for filenames
  matching each UTC day; days with no matching file are recorded as
  ``SKIPPED_NO_INPUT``.
- ``--output-dir PATH`` — directory where CDF files are written.

Optional arguments
------------------

- ``--telemetry-file PATH`` — append-only telemetry CSV. Defaults to
  ``<input-dir>/download_telemetry.csv`` (the same file Phase 1
  writes). Use this only if you keep telemetry separate from the
  download artifacts.
- ``--sensor-id`` — REACH sensor identifier or ``ALL`` (default).
  Drives the input filename pattern.
- ``--descriptor`` — UDL descriptor (default ``QUICKLOOK``).
- ``--output-format`` — input serialization format (default ``csv``).
- ``--retry-failed`` — re-attempt days whose latest telemetry status
  is ``FAILED``.
- ``--limit-days N`` — cap attempted days, counted from the first
  day in the range that is not already complete.
- ``--dry-run`` — plan only: log per-day actions, write no telemetry,
  do no work.
- ``-v`` / ``-vv`` — increase logging verbosity.

S3 upload arguments
-------------------

- ``--upload-to-s3`` — when set, uploads each successful CDF to S3
  via :func:`sdc_aws_utils.aws.push_science_file`. ``UPLOADED`` is the
  terminal status. Without this flag, ``PROCESSED`` is terminal.
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

Status lifecycle
================

Phase 2 introduces stage-prefixed pending statuses so the row
indicates which stage was interrupted:

- ``PROCESS_PENDING`` — process_file invocation in progress.
- ``PROCESSED`` — CDF written to disk. Terminal in local-only mode.
- ``UPLOAD_PENDING`` — S3 upload in progress.
- ``UPLOADED`` — CDF successfully uploaded. Terminal in upload mode.
- ``SKIPPED_NO_INPUT`` — no matching CSV for the day in
  ``--input-dir``. Re-runnable: the day is re-attempted if the input
  later appears.

Phase 1 statuses (``DOWNLOAD_PENDING``, ``DOWNLOADED``,
``SKIPPED_NO_DATA``) are treated as "no prior process-stage row" by
the resume logic.

Telemetry schema
================

Phase 2 extends the Phase 1 download telemetry CSV with these
columns (all default to ``""`` for older rows):

- ``process_seconds`` — wall-clock seconds spent in
  :func:`process_file`.
- ``cdf_size_mb`` — size of the produced CDF in megabytes.
- ``cdf_path`` — local path of the CDF.
- ``upload_seconds`` — wall-clock seconds spent in the S3 upload.
- ``s3_bucket`` — destination bucket reported on a successful
  upload.
- ``s3_key`` — S3 key returned by
  :func:`sdc_aws_utils.aws.push_science_file`.

Restart semantics
=================

Resume rules per UTC day, based on the most-recent telemetry row:

- ``UPLOADED`` → skip (terminal).
- ``PROCESSED`` + CDF on disk + upload mode → upload only.
- ``PROCESSED`` + CDF on disk + local-only mode → skip (terminal).
- ``PROCESSED`` + CDF missing → re-process from CSV.
- ``UPLOAD_PENDING`` + CDF on disk → upload only.
- ``UPLOAD_PENDING`` + CDF missing → re-process from CSV.
- ``PROCESS_PENDING`` → re-process from CSV.
- ``FAILED`` → skip unless ``--retry-failed``.
- ``SKIPPED_NO_INPUT`` → re-attempt if CSV is now present.
- Phase 1 statuses → re-process from CSV.

Operator runbook
================

Process succeeded but upload failed
   The day's row sequence ends in ``UPLOAD_PENDING`` then ``FAILED``
   with a populated ``error_type`` / ``error_message``. The CDF is
   on disk in ``--output-dir``. Resolve the cause (creds, bucket
   access, etc.), then rerun with ``--retry-failed``: the
   orchestrator detects the existing CDF and uploads only.

Process failed mid-day
   The day's row sequence ends in ``PROCESS_PENDING`` then
   ``FAILED``. Inspect the error fields, fix the underlying issue,
   then rerun with ``--retry-failed``.

CDF accidentally deleted
   Delete the CDF from ``--output-dir`` and rerun without
   ``--retry-failed``. The orchestrator detects the missing CDF and
   re-processes from the CSV automatically.

Notes & caveats
===============

- ``process_file`` writes to ``Path.cwd()`` when
  ``LAMBDA_ENVIRONMENT`` is unset, which is always the case for a
  historical local run. The orchestrator chdir's into
  ``--output-dir`` for the duration of each call and restores the
  prior cwd in ``finally``.
- When the same telemetry CSV is shared with Phase 1 (recommended),
  rerunning the ``download`` subcommand after ``process`` continues
  to behave correctly because ``download`` only consults Phase 1
  statuses for resume.
