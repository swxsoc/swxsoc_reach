"""Local CDF upload helper for the historical process orchestrator.

Mirrors the executor Lambda's ``_upload_reach_file_to_s3`` exactly:
sets ``SWXSOC_MISSION=swxsoc_pipeline``, calls
:func:`swxsoc._reconfigure`, and delegates the upload to
:func:`sdc_aws_utils.aws.push_science_file`.

``push_science_file`` (via :func:`sdc_aws_utils.aws.upload_file_to_s3`)
hard-codes ``/tmp/{filename}`` as the source path because it was
written for the Lambda runtime where the CDF already lives in
``/tmp``. For a local historical run the CDF is in
``--output-dir`` instead, so this helper stages a copy of the file
into ``/tmp`` before invoking ``push_science_file`` and removes the
staged copy afterwards. The original CDF in ``--output-dir`` is left
untouched.

``boto3`` and ``sdc_aws_utils`` are imported lazily inside the
function so the package still imports on dev machines that have not
installed the ``[net]`` extra.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from swxsoc_reach import log

_INSTALL_HINT = (
    "S3 upload requires the optional 'net' extra: "
    "pip install 'swxsoc_reach[net]' (provides boto3 + sdc_aws_utils)."
)


def upload_cdf_to_s3(cdf_path: Path, *, destination_bucket: str) -> tuple[str, str]:
    """Upload a single CDF file to S3 via ``sdc_aws_utils``.

    Parameters
    ----------
    cdf_path : pathlib.Path
        Local path to the CDF file. Must exist on disk.
    destination_bucket : str
        Target S3 bucket name (no ``s3://`` prefix).

    Returns
    -------
    tuple[str, str]
        ``(destination_bucket, s3_key)`` where ``s3_key`` is the value
        returned by :func:`sdc_aws_utils.aws.push_science_file`.

    Raises
    ------
    RuntimeError
        If ``boto3`` or ``sdc_aws_utils`` are not importable. The
        message includes the install hint.
    FileNotFoundError
        If ``cdf_path`` does not exist.
    """
    cdf_path = Path(cdf_path)
    if not cdf_path.is_file():
        raise FileNotFoundError(f"CDF not found for upload: {cdf_path}")

    try:
        import boto3  # noqa: F401  -- imported for availability check
        from sdc_aws_utils.aws import push_science_file
        from sdc_aws_utils.config import parser as science_filename_parser
    except ImportError as exc:  # pragma: no cover - exercised via test stub
        raise RuntimeError(f"{_INSTALL_HINT} (import error: {exc})") from exc

    # ``upload_file_to_s3`` (called inside push_science_file) reads from
    # ``/tmp/{basename}``. Stage the file there for the duration of the
    # upload, then remove the staging copy.
    filename = cdf_path.name
    tmp_dir = Path(tempfile.gettempdir())
    staged = tmp_dir / filename
    if staged.resolve() != cdf_path.resolve():
        shutil.copy2(cdf_path, staged)
        staged_was_copied = True
    else:
        staged_was_copied = False

    try:
        s3_key = push_science_file(
            science_filename_parser=science_filename_parser,
            destination_bucket=destination_bucket,
            calibrated_filename=filename,
        )
    finally:
        if staged_was_copied:
            try:
                staged.unlink()
            except OSError as exc:
                log.warning(f"Failed to remove staged upload {staged}: {exc}")

    log.info(
        "Uploaded REACH CDF to S3",
        extra={
            "cdf_path": str(cdf_path),
            "destination_bucket": destination_bucket,
            "s3_key": s3_key,
        },
    )
    return destination_bucket, s3_key
