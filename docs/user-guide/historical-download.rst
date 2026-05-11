.. _historical-download:

***************************
Historical UDL Download CLI
***************************

The ``swxsoc_reach`` package ships a command-line tool for downloading
REACH data from the Unified Data Library (UDL) over arbitrary historical
date ranges. Unlike the scheduled Lambda path
(:func:`~swxsoc_reach.net.udl.download_UDL_reach_to_file`), the CLI takes
absolute UTC dates and writes one artifact per day, with append-only
telemetry that supports safe restart and resume.

The CLI is accessed via Python's ``-m`` module flag:

.. code-block:: console

   python -m swxsoc_reach download --help


Quick start
===========

Download two days of data for a single sensor:

.. code-block:: console

   BASICAUTH="Basic <token>" python -m swxsoc_reach download \
     --start-date 2026-01-01 \
     --end-date   2026-01-02 \
     --sensor-id  REACH-1 \
     --output-dir ./out


Resolving UDL credentials
=========================

The CLI obtains the UDL HTTP Basic auth credential at startup via
:func:`swxsoc_reach.net.auth.resolve_udl_auth`. Resolution order:

1. The ``BASICAUTH`` environment variable, if set, is used directly
   (local-dev / pre-exported credential).
2. Otherwise, if ``SECRET_ARN_UDL`` is set, the secret is fetched from
   AWS Secrets Manager (using ``boto3``'s standard credential and
   region resolution chain) and its ``basicauth`` JSON field is used.
   The resolved value is also written back to ``os.environ['BASICAUTH']``.
3. Otherwise the CLI exits with code ``2`` and a clear error message.

``boto3`` is an optional dependency under the ``net`` extra:

.. code-block:: console

   pip install 'swxsoc_reach[net]'

If you only ever use ``BASICAUTH`` (path 1), ``boto3`` is not required.


Required arguments
==================

``--start-date YYYY-MM-DD``
   Inclusive UTC start date.

``--end-date YYYY-MM-DD``
   Inclusive UTC end date.

``--output-dir PATH``
   Directory where per-day artifacts are written. Created if missing.


Common options
==============

``--telemetry-file PATH``
   Path to the append-only telemetry CSV. Defaults to
   ``<output-dir>/download_telemetry.csv``.

``--sensor-id ID``
   REACH sensor identifier or ``ALL`` (default ``ALL``). Drives chunk
   size in
   :func:`~swxsoc_reach.net.udl.get_reach_datetimelist`:

   - ``ALL`` → ~288 UDL requests/day (5-minute chunks).
   - A specific sensor (e.g. ``REACH-1``) → ~4 UDL requests/day
     (6-hour chunks).

``--descriptor NAME``
   UDL ``descriptor`` query value (default ``QUICKLOOK``).

``--output-format {csv,json}``
   Output serialization format (default ``csv``).

``--retry-failed``
   Re-attempt days whose latest telemetry status is ``FAILED``.
   Without this flag, ``FAILED`` days are skipped on restart.

``--limit-days N``
   Cap the number of days actually attempted, counted from the first
   day in the range that is not already ``DOWNLOADED`` with its CSV on
   disk. Composes naturally with resume.

``--dry-run``
   Plan only: log per-day actions, write no telemetry, no network
   calls. Does not require auth.

``--aws-region REGION``
   Optional AWS region override for the Secrets Manager lookup.

``-v`` / ``-vv``
   Increase logging verbosity.


AIMD rate-controller flags
==========================

These knobs are forwarded to
:func:`~swxsoc_reach.net.udl.download_UDL_reach_window` and tune the
adaptive (Additive Increase / Multiplicative Decrease) request rate
used by the per-day downloader. The defaults are the same as the
Lambda path; an ``ALL`` historical backfill (≈288 req/day) typically
benefits from raising ``--max-concurrent-requests`` and
``--initial-rate``.

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Flag
     - Default
   * - ``--max-concurrent-requests``
     - 4
   * - ``--initial-rate``
     - 5.0 req/s
   * - ``--additive-increase``
     - 1.0
   * - ``--multiplicative-decrease``
     - 0.5
   * - ``--min-rate``
     - 5.0 req/s
   * - ``--max-rate``
     - 25.0 req/s


Restart and resume semantics
============================

The CLI is idempotent. On every run it loads the telemetry CSV and,
for each day in the requested range, picks an action:

.. list-table::
   :header-rows: 1
   :widths: 30 25 45

   * - Latest prior status
     - Artifact present?
     - Action
   * - *(no row)*
     - n/a
     - run
   * - ``DOWNLOADED``
     - yes
     - skip (idempotent)
   * - ``DOWNLOADED``
     - no
     - re-download
   * - ``SKIPPED_NO_DATA``
     - n/a
     - skip (terminal)
   * - ``FAILED``
     - n/a
     - skip, unless ``--retry-failed``
   * - ``DOWNLOAD_PENDING``
     - n/a
     - re-run (interrupted)


Telemetry CSV schema
====================

One row is appended per attempt. Older rows for the same date are
preserved; ``HistoricalTelemetry.load_state`` returns the most-recent
row per ``chunk_date_utc`` (file order breaks ties).

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Column
     - Description
   * - ``run_id``
     - UUID4 stamped on every row written by a single CLI invocation.
   * - ``chunk_date_utc``
     - ``YYYY-MM-DD`` (UTC).
   * - ``window_start_utc``
     - ISO 8601 UTC, inclusive (``00:00:00`` of ``chunk_date_utc``).
   * - ``window_end_utc``
     - ISO 8601 UTC, exclusive (``window_start + 86400 s``).
   * - ``status``
     - ``DOWNLOAD_PENDING`` | ``DOWNLOADED`` | ``SKIPPED_NO_DATA`` |
       ``FAILED``. Phase 2 (process / upload) writes additional
       statuses (``PROCESS_PENDING``, ``PROCESSED``,
       ``UPLOAD_PENDING``, ``UPLOADED``, ``SKIPPED_NO_INPUT``) to the
       same file — see :ref:`historical-process`.
   * - ``records_downloaded``
     - Number of records in the written artifact.
   * - ``expected_records``
     - Per-sensor upper-bound baseline (``ALL`` → 1,105,920;
       single sensor → 34,560).
   * - ``availability_pct``
     - ``records_downloaded / expected_records * 100``.
   * - ``download_seconds``
     - Wall-clock seconds for the per-day attempt.
   * - ``csv_size_mb``
     - Size of the written artifact in MiB.
   * - ``csv_path``
     - Absolute path of the written artifact (``DOWNLOADED`` only).
   * - ``sensor_id``, ``descriptor``, ``output_format``
     - Echo of the run inputs.
   * - ``error_type``, ``error_message``
     - Populated on ``FAILED`` (and ``error_message`` on
       ``SKIPPED_NO_DATA``).
   * - ``started_at_utc``, ``finished_at_utc``
     - ISO 8601 UTC timestamps for the attempt.


Exit codes
==========

- ``0`` — every planned day succeeded or was a known skip.
- ``1`` — at least one day ended in ``FAILED``.
- ``2`` — usage / configuration error (auth resolution failed,
  inverted date range, etc.).


Running via Docker
==================

The team's existing Docker image ships ``swxsoc_reach`` pre-installed.
Override the entrypoint to invoke the CLI:

.. code-block:: console

   docker run --rm -it \
     -e SECRET_ARN_UDL=$SECRET_ARN_UDL \
     -e AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
     -e AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
     -e AWS_SESSION_TOKEN=$AWS_SESSION_TOKEN \
     -v /local/output:/output_dir \
     --entrypoint python <team-image>:latest \
     -m swxsoc_reach download \
       --start-date 2026-01-01 \
       --end-date   2026-01-31 \
       --sensor-id  ALL \
       --output-dir /output_dir


Operator runbook: interrupted runs
==================================

If a multi-day run is interrupted (Ctrl-C, container killed, network
loss):

1. The telemetry CSV in ``--output-dir`` is consistent on disk
   (``fsync`` after every row).
2. Days that were mid-flight at interrupt time will have a
   ``DOWNLOAD_PENDING`` row as their latest entry — these will be
   **re-run** on the next invocation.
3. Days that completed normally have a ``DOWNLOADED`` row plus their
   artifact on disk and will be **skipped** on the next invocation.
4. To pick up where you left off, simply re-run the same command.
   Add ``--retry-failed`` if you also want to re-attempt days that
   ended in ``FAILED``.

To inspect progress without running anything, use ``--dry-run``:

.. code-block:: console

   python -m swxsoc_reach download \
     --start-date 2026-01-01 --end-date 2026-01-31 \
     --output-dir ./out --dry-run -v
