"""Command-line entry point for ``python -m swxsoc_reach``.

Exposes two subcommands:

- ``download`` — historical UDL download orchestrator
- ``process``  — historical CSV → CDF processor with optional S3 upload.

The argparse layout uses *subparsers* so future subcommands can be
added without changing existing flags.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Sequence

from swxsoc_reach import log
from swxsoc_reach.historical.download_orchestrator import (
    DownloadRunConfig,
    run_download,
)
from swxsoc_reach.historical.process_orchestrator import (
    ProcessRunConfig,
    run_process,
)
from swxsoc_reach.historical.telemetry import valid_levels
from swxsoc_reach.net.auth import resolve_udl_auth


def _parse_iso_date(value: str) -> date:
    """argparse type for ``YYYY-MM-DD`` UTC dates."""
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"{value!r} is not a valid YYYY-MM-DD date"
        ) from exc


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m swxsoc_reach",
        description=(
            "swxsoc_reach command-line tools: 'download' drives the "
            "historical UDL downloader, 'process' converts the resulting "
            "CSVs into CDFs and (optionally) uploads them to S3."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_download_subparser(subparsers)
    _add_process_subparser(subparsers)
    return parser


def _add_download_subparser(subparsers: argparse._SubParsersAction) -> None:
    dl = subparsers.add_parser(
        "download",
        help="Historical UDL download over an inclusive UTC date range.",
        description=(
            "Drive a per-day UDL download over [start-date, end-date] UTC, "
            "inclusive. Each day produces one CSV/JSON artifact under "
            "--output-dir plus telemetry rows in --telemetry-file. Reruns "
            "are idempotent: days already DOWNLOADED with their artifact "
            "on disk are skipped. Per-day request count: sensor_id=ALL "
            "uses ~288 UDL requests/day (5-min chunks); a specific "
            "sensor uses ~4/day (6-hour chunks)."
        ),
    )

    dl.add_argument(
        "--start-date",
        required=True,
        type=_parse_iso_date,
        help="Inclusive UTC start date (YYYY-MM-DD).",
    )
    dl.add_argument(
        "--end-date",
        required=True,
        type=_parse_iso_date,
        help="Inclusive UTC end date (YYYY-MM-DD).",
    )
    dl.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where per-day artifacts are written.",
    )
    dl.add_argument(
        "--telemetry-file",
        type=Path,
        default=None,
        help=(
            "Path to the append-only telemetry CSV. "
            "Defaults to <output-dir>/download_telemetry.csv."
        ),
    )
    dl.add_argument(
        "--sensor-id",
        default="ALL",
        help="REACH sensor identifier or 'ALL' (default: ALL).",
    )
    dl.add_argument(
        "--descriptor",
        choices=["QUICKLOOK", "PROVISIONAL"],
        default="QUICKLOOK",
        help="UDL descriptor query value (default: QUICKLOOK).",
    )
    dl.add_argument(
        "--output-format",
        choices=["csv", "json"],
        default="csv",
        help="Output serialization format (default: csv).",
    )
    dl.add_argument(
        "--retry-failed",
        action="store_true",
        help="Re-attempt days whose latest telemetry status is FAILED.",
    )
    dl.add_argument(
        "--limit-days",
        type=int,
        default=None,
        help=(
            "Cap the number of days actually attempted, counted from the "
            "first day in the range that is not already DOWNLOADED."
        ),
    )
    dl.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only: log per-day actions, write no telemetry, no network.",
    )
    dl.add_argument(
        "--aws-region",
        default=None,
        help=(
            "Optional AWS region for the Secrets Manager lookup. Defaults "
            "to boto3's standard region resolution chain."
        ),
    )
    dl.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v INFO, -vv DEBUG).",
    )

    aimd = dl.add_argument_group(
        "AIMD rate controller",
        "Tuning for the per-day downloader's adaptive request rate.",
    )
    aimd.add_argument("--max-concurrent-requests", type=int, default=4)
    aimd.add_argument("--initial-rate", type=float, default=5.0)
    aimd.add_argument("--additive-increase", type=float, default=1.0)
    aimd.add_argument("--multiplicative-decrease", type=float, default=0.5)
    aimd.add_argument("--min-rate", type=float, default=5.0)
    aimd.add_argument("--max-rate", type=float, default=25.0)


def _add_process_subparser(subparsers: argparse._SubParsersAction) -> None:
    pr = subparsers.add_parser(
        "process",
        help="Historical CSV → CDF processor (with optional S3 upload).",
        description=(
            "Convert per-day UDL CSVs (produced by 'download') into CDFs "
            "and optionally upload them to S3 via sdc_aws_utils. Inputs "
            "are discovered by globbing --input-dir for filenames "
            "matching each UTC day in [start-date, end-date]. Reuses the "
            "Phase 1 telemetry CSV (extended schema) so the full "
            "download → process → upload lifecycle is in one file."
        ),
    )
    pr.add_argument(
        "--start-date",
        required=True,
        type=_parse_iso_date,
        help="Inclusive UTC start date (YYYY-MM-DD).",
    )
    pr.add_argument(
        "--end-date",
        required=True,
        type=_parse_iso_date,
        help="Inclusive UTC end date (YYYY-MM-DD).",
    )
    pr.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory holding Phase 1 download artifacts (CSV/JSON).",
    )
    pr.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory where CDF files are written.",
    )
    pr.add_argument(
        "--telemetry-file",
        type=Path,
        default=None,
        help=(
            "Path to the append-only telemetry CSV. Defaults to "
            "<input-dir>/download_telemetry.csv (the same file Phase 1 "
            "writes)."
        ),
    )
    pr.add_argument(
        "--sensor-id",
        default="ALL",
        help="REACH sensor identifier or 'ALL' (default: ALL).",
    )
    pr.add_argument(
        "--descriptor",
        choices=["QUICKLOOK", "PRELIMINARY"],
        default="QUICKLOOK",
        help="UDL descriptor query value (default: QUICKLOOK).",
    )
    pr.add_argument(
        "--output-format",
        choices=["csv", "json"],
        default="csv",
        help="Input serialization format on disk (default: csv).",
    )
    pr.add_argument(
        "--target-level",
        choices=list(valid_levels()),
        default="l1c",
        help="Output data level to produce (default: l1c).",
    )
    pr.add_argument(
        "--retry-failed",
        action="store_true",
        help="Re-attempt days whose latest telemetry status is FAILED.",
    )
    pr.add_argument(
        "--limit-days",
        type=int,
        default=None,
        help=(
            "Cap on attempted days, counted from the first day in the "
            "range that is not already complete."
        ),
    )
    pr.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only: log per-day actions, write no telemetry, no work.",
    )
    pr.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase logging verbosity (-v INFO, -vv DEBUG).",
    )

    s3 = pr.add_argument_group(
        "S3 upload",
        "Optional upload of the produced CDF to S3 via sdc_aws_utils.",
    )
    s3.add_argument(
        "--upload-to-s3",
        action="store_true",
        help="Upload each successful CDF to S3 (requires --s3-bucket).",
    )
    s3.add_argument(
        "--s3-bucket",
        default=None,
        help="Destination S3 bucket name (required iff --upload-to-s3).",
    )
    s3.add_argument(
        "--aws-region",
        default=None,
        help="Optional AWS region. Defaults to boto3's standard chain.",
    )


def _configure_logging(verbosity: int) -> None:
    """Map -v/-vv to logging levels on the package logger."""
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG
    log.setLevel(level)


def _download_config_from_args(
    args: argparse.Namespace, auth_token: str
) -> DownloadRunConfig:
    telemetry_path = (
        args.telemetry_file
        if args.telemetry_file is not None
        else args.output_dir / "download_telemetry.csv"
    )
    return DownloadRunConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        output_dir=args.output_dir,
        telemetry_path=telemetry_path,
        sensor_id=args.sensor_id,
        descriptor=args.descriptor,
        output_format=args.output_format,
        retry_failed=args.retry_failed,
        limit_days=args.limit_days,
        dry_run=args.dry_run,
        auth_token=auth_token,
        max_concurrent_requests=args.max_concurrent_requests,
        initial_rate=args.initial_rate,
        additive_increase=args.additive_increase,
        multiplicative_decrease=args.multiplicative_decrease,
        min_rate=args.min_rate,
        max_rate=args.max_rate,
    )


def _run_download_command(args: argparse.Namespace) -> int:
    if args.dry_run:
        # Dry-run plans only; don't require auth.
        auth_token = ""
    else:
        try:
            auth_token = resolve_udl_auth(region_name=args.aws_region)
        except RuntimeError as exc:
            log.error(f"UDL auth resolution failed: {exc}")
            return 2

    if args.end_date < args.start_date:
        log.error(
            f"--end-date ({args.end_date.isoformat()}) must be on or after "
            f"--start-date ({args.start_date.isoformat()})."
        )
        return 2

    config = _download_config_from_args(args, auth_token)
    # Log the Config for visibility
    log.info(f"Starting download with config: {config}")
    summary = run_download(config)
    log.info(
        f"Run {summary.run_id} complete: "
        f"planned={summary.days_planned} "
        f"downloaded={summary.days_downloaded} "
        f"skipped_existing={summary.days_skipped_existing} "
        f"skipped_no_data={summary.days_skipped_no_data} "
        f"failed={summary.days_failed}"
    )
    # Exit non-zero if any day failed so operators can detect it from
    # shell / CI without parsing logs.
    return 1 if summary.days_failed > 0 else 0


def _process_config_from_args(args: argparse.Namespace) -> ProcessRunConfig:
    telemetry_path = (
        args.telemetry_file
        if args.telemetry_file is not None
        else args.input_dir / "download_telemetry.csv"
    )
    return ProcessRunConfig(
        start_date=args.start_date,
        end_date=args.end_date,
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        telemetry_path=telemetry_path,
        sensor_id=args.sensor_id,
        descriptor=args.descriptor,
        output_format=args.output_format,
        retry_failed=args.retry_failed,
        limit_days=args.limit_days,
        dry_run=args.dry_run,
        upload_to_s3=args.upload_to_s3,
        s3_bucket=args.s3_bucket,
    )


def _run_process_command(
    args: argparse.Namespace, parser: argparse.ArgumentParser
) -> int:
    if args.upload_to_s3 and not args.s3_bucket:
        parser.error("--upload-to-s3 requires --s3-bucket")
    if args.end_date < args.start_date:
        log.error(
            f"--end-date ({args.end_date.isoformat()}) must be on or after "
            f"--start-date ({args.start_date.isoformat()})."
        )
        return 2

    config = _process_config_from_args(args)
    # Log the Config for visibility
    log.info(f"Starting process with config: {config}")
    summary = run_process(config)
    log.info(
        f"Run {summary.run_id} complete: "
        f"planned={summary.days_planned} "
        f"processed={summary.days_processed} "
        f"uploaded={summary.days_uploaded} "
        f"files_processed={summary.files_processed} "
        f"files_uploaded={summary.files_uploaded} "
        f"skipped_existing={summary.days_skipped_existing} "
        f"skipped_no_input={summary.days_skipped_no_input} "
        f"failed={summary.days_failed}"
    )
    return 1 if summary.days_failed > 0 else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for ``python -m swxsoc_reach``.

    Returns the process exit code: ``0`` on full success, ``1`` if any
    day ended in ``FAILED``, ``2`` for usage / config errors.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    if args.command == "download":
        return _run_download_command(args)
    if args.command == "process":
        return _run_process_command(args, parser)

    parser.error(f"Unknown command: {args.command}")
    return 2  # unreachable; parser.error exits


if __name__ == "__main__":
    sys.exit(main())
