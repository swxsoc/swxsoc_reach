"""UDL authentication helpers.

Resolves the UDL HTTP Basic auth credential used by
:func:`swxsoc_reach.net.udl.download_UDL_reach_window` (and the legacy
relative-time wrapper). Two sources are supported, in priority order:

1. The ``BASICAUTH`` environment variable (local-dev fallback / what an
   operator pre-exports).
2. AWS Secrets Manager via ``SECRET_ARN_UDL`` — the secret's
   ``SecretString`` is parsed as JSON and the ``basicauth`` field is
   used. This matches the existing scheduled-Lambda pattern.

``boto3`` is imported lazily inside :func:`resolve_udl_auth` so this
module remains importable on environments where ``boto3`` is not
installed (e.g. running the package without the ``net`` extra and
relying on a pre-set ``BASICAUTH``).
"""

from __future__ import annotations

import json
import os

from swxsoc_reach import log

_BASICAUTH_ENV = "BASICAUTH"
_SECRET_ARN_ENV = "SECRET_ARN_UDL"
_SECRET_KEY = "basicauth"


def resolve_udl_auth(region_name: str | None = None) -> str:
    """Resolve the UDL HTTP Basic auth credential.

    Resolution order:

    1. If ``BASICAUTH`` is set in the environment, return it directly
       and do not touch AWS.
    2. Else if ``SECRET_ARN_UDL`` is set, fetch the secret from AWS
       Secrets Manager, parse its ``SecretString`` as JSON, extract the
       ``basicauth`` field, write it back to ``os.environ['BASICAUTH']``
       (so downstream code that reads the env var continues to work
       unchanged), and return it.
    3. Else raise :class:`RuntimeError`.

    Parameters
    ----------
    region_name : str or None, optional
        Optional AWS region passed to ``boto3.session.Session``. When
        ``None``, ``boto3``'s standard region resolution chain is used
        (``AWS_REGION`` / ``AWS_DEFAULT_REGION`` / config file).

    Returns
    -------
    str
        The UDL HTTP Basic auth credential value.

    Raises
    ------
    RuntimeError
        If neither ``BASICAUTH`` nor ``SECRET_ARN_UDL`` is set, if the
        ``boto3`` package is not installed when Secrets Manager
        resolution is attempted, or if the secret payload does not
        contain a ``basicauth`` key.
    """
    pre_set = os.environ.get(_BASICAUTH_ENV)
    if pre_set:
        log.info("Using UDL credential from BASICAUTH environment variable")
        return pre_set

    secret_arn = os.environ.get(_SECRET_ARN_ENV)
    if not secret_arn:
        raise RuntimeError(
            f"UDL credential not found. Set either {_BASICAUTH_ENV} (direct "
            f"value) or {_SECRET_ARN_ENV} (AWS Secrets Manager ARN containing "
            f"a JSON object with a '{_SECRET_KEY}' key)."
        )

    try:
        import boto3  # lazy import: optional dependency in [net] extra
    except ImportError as exc:
        raise RuntimeError(
            f"{_SECRET_ARN_ENV} is set but boto3 is not installed. Install "
            "the 'net' extra (pip install 'swxsoc_reach[net]') or set "
            f"{_BASICAUTH_ENV} directly."
        ) from exc

    session = boto3.session.Session(region_name=region_name)
    client = session.client(service_name="secretsmanager")
    response = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])

    if _SECRET_KEY not in secret:
        raise RuntimeError(
            f"Secret at {_SECRET_ARN_ENV} does not contain required key "
            f"'{_SECRET_KEY}'."
        )

    value = secret[_SECRET_KEY]
    # Mirror existing Lambda pattern: populate BASICAUTH for any
    # downstream code that reads the env var directly.
    os.environ[_BASICAUTH_ENV] = value
    log.info("Resolved UDL credential from AWS Secrets Manager")
    return value
