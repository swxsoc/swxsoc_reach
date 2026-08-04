"""
Local CDF upload helper for the historical process orchestrator.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from swxsoc.io.s3 import push_science_file
from swxsoc.util.util import parse_science_filename

from swxsoc_reach import log


def upload_cdf_to_s3(cdf_path: Path, *, destination_bucket: str) -> tuple[str, str]:
    """Upload a single CDF file to S3 via ``swxsoc.io.s3.push_science_file``.

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
        returned by :func:`swxsoc.io.s3.push_science_file`.

    Raises
    ------
    FileNotFoundError
        If ``cdf_path`` does not exist.
    """
    cdf_path = Path(cdf_path)
    if not cdf_path.is_file():
        raise FileNotFoundError(f"CDF not found for upload: {cdf_path}")

    # ``swxsoc.io.s3.push_science_file`` (via :func:``swxsoc.io.s3.upload_file_to_s3``)
    # hard-codes ``/tmp/{filename}`` as the source path because it was
    # written for the Lambda runtime where the CDF already lives in
    # ``/tmp``. For a local historical run the CDF is in
    # ``--output-dir`` instead, so this helper stages a copy of the file
    # into ``/tmp`` before invoking ``push_science_file`` and removes the
    # staged copy afterwards. The original CDF in ``--output-dir`` is left
    # untouched.
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
            science_filename_parser=parse_science_filename,
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
