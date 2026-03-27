import json
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal
from pathlib import Path
import requests
from astropy.time import Time, TimeDelta

from swxsoc_reach import log


def format_udl_timestamp(value: Time) -> str:
    """Format an Astropy time value for UDL query parameters.

    Parameters
    ----------
    value : astropy.time.Time
        Timestamp to convert into the UDL API timestamp format.

    Returns
    -------
    str
        Timestamp formatted as ``YYYY-MM-DDTHH:MM:SS.000Z``.
    """
    return f"{value.isot.split('.')[0]}.000Z"


def get_reach_datetimelist(
    start_time: Time, end_time: Time, sensor_id: str
) -> list[str]:
    """Split a time range into UDL-safe query windows.

    Parameters
    ----------
    start_time : astropy.time.Time
        Inclusive start time of the requested observation window.
    end_time : astropy.time.Time
        Inclusive end time of the requested observation window.
    sensor_id : str
        REACH sensor identifier. IDs beginning with ``REACH-`` use 6-hour
        chunks; all other values use 10-minute chunks.

    Returns
    -------
    list[str]
        List of ``obTime`` interval strings in UDL range format
        (``<start>..<end>``).
    """
    timechunk = 21600 if sensor_id.startswith("REACH-") else 600
    dtlist = []
    total_seconds = int(round((end_time - start_time).to_value("sec")))

    for chunk_start_offset in range(0, total_seconds, timechunk):
        chunk_end_offset = min(chunk_start_offset + timechunk, total_seconds)

        if chunk_start_offset == 0:
            chunk_start = start_time
        else:
            chunk_start = start_time + TimeDelta(chunk_start_offset + 1, format="sec")

        chunk_end = start_time + TimeDelta(chunk_end_offset, format="sec")
        dtlist.append(
            f"{format_udl_timestamp(chunk_start)}..{format_udl_timestamp(chunk_end)}"
        )

    return dtlist


def get_reach_urllist(
    dtlist: list[str], sensor_id: str, descriptor: str
) -> dict[str, str]:
    """Build UDL request URLs for each time interval.

    Parameters
    ----------
    dtlist : list[str]
        List of UDL ``obTime`` interval strings.
    sensor_id : str
        REACH sensor identifier, or ``ALL`` for all sensors.
    descriptor : str
        UDL descriptor value to include in the query.

    Returns
    -------
    dict[str, str]
        Mapping of each interval string to its full UDL query URL.
    """
    baseurl = "https://unifieddatalibrary.com/udl/spaceenvobservation"
    urls = {}

    for obtime in dtlist:
        if sensor_id.upper() == "ALL":
            url = (
                f"{baseurl}?obTime={obtime}&source=Aerospace&dataMode=REAL"
                f"&descriptor={descriptor}&sort=obTime"
            )
        else:
            url = (
                f"{baseurl}?obTime={obtime}&idSensor={sensor_id}&source=Aerospace"
                f"&dataMode=REAL&descriptor={descriptor}&sort=obTime"
            )
        urls[obtime] = url

    return urls


def build_reach_output_filename(
    sensor_id: str,
    start_time: Time,
    end_time: Time,
    output_format: Literal["json", "csv"],
) -> str:
    """Build a deterministic output filename for combined REACH data.

    Parameters
    ----------
    sensor_id : str
        REACH sensor identifier, or ``ALL``.
    start_time : astropy.time.Time
        Start time used in the query.
    end_time : astropy.time.Time
        End time used in the query.
    output_format : {'json', 'csv'}
        Output serialization format.

    Returns
    -------
    str
        Filename with sensor prefix and query time range.
    """
    sensor_prefix = "REACH-ALL" if sensor_id.upper() == "ALL" else sensor_id
    time_range = (
        f"{start_time.strftime('%Y%m%dT%H%M%S')}_{end_time.strftime('%Y%m%dT%H%M%S')}"
    )
    return f"{sensor_prefix}_{time_range}.{output_format}"


def write_reach_output(
    filepath: Path,
    obs: list[dict[str, Any]],
    output_format: Literal["json", "csv"],
) -> None:
    """Write REACH payload records to disk.

    Parameters
    ----------
    filepath : pathlib.Path
        Destination file path.
    obs : list[dict[str, Any]]
        Observation records to serialize.
    output_format : {'json', 'csv'}
        Output serialization format.

    Returns
    -------
    None
        This function writes a file as a side effect.
    """
    if output_format == "json":
        with open(filepath, "w", encoding="utf-8") as json_file:
            json.dump(obs, json_file, indent=4)
        return

    if not obs:
        with open(filepath, "w", newline="", encoding="utf-8") as csv_file:
            csv_file.write("")
        return

    fieldnames = obs[0].keys()
    with open(filepath, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(obs)


def fetch_reach_chunk(
    dt: str,
    url: str,
    auth_token: str,
    timeout_seconds: int = 120,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch one UDL chunk and normalize the payload into a list of records.

    Parameters
    ----------
    dt : str
        Chunk window identifier (``<start>..<end>``) used for logging/order.
    url : str
        UDL request URL for the chunk.
    auth_token : str
        Authorization header value for UDL.
    timeout_seconds : int, optional
        Request timeout in seconds.
        Default is 120 seconds to allow for large chunks or slow responses.

    Returns
    -------
    tuple[str, list[dict[str, Any]]]
        The chunk window string and its records.

    Raises
    ------
    requests.HTTPError
        If UDL responds with an unsuccessful status code.
    """
    response = requests.get(
        url,
        headers={"Authorization": auth_token},
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    obs_chunk = response.json()
    if isinstance(obs_chunk, list):
        normalized = obs_chunk
    elif obs_chunk:
        normalized = [obs_chunk]
    else:
        normalized = []

    return dt, normalized


def download_UDL_reach_to_file(
    auth_token: str,
    sensor_id: str,
    descriptor: str,
    output_format: Literal["json", "csv"],
    delay_seconds: int,
    window_seconds: int,
    output_dir: Path | str,
    max_concurrent_requests: int = 4,
) -> Path:
    """Download REACH data from UDL and write one combined output file.

    Parameters
    ----------
    auth_token : str
        UDL authorization token value for the ``Authorization`` header.
    sensor_id : str
        REACH sensor identifier, or ``ALL``.
    descriptor : str
        UDL descriptor value to include in each request.
    output_format : {'json', 'csv'}
        Output serialization format.
    delay_seconds : int
        Number of seconds to subtract from ``Time.now()`` before ending the
        query window.
    window_seconds : int
        Duration of the query window in seconds.
    output_dir : pathlib.Path or str
        Directory where the combined output file is written.
    max_concurrent_requests : int, optional
        Maximum number of chunk requests to run concurrently. Lower values are
        safer for unknown API limits; higher values can improve throughput.

    Returns
    -------
    pathlib.Path
        Absolute or relative path (as provided) to the written output file.

    Raises
    ------
    ValueError
        If ``output_format`` is not one of ``'json'`` or ``'csv'``.
    requests.HTTPError
        If any UDL request returns an unsuccessful HTTP status code.
    """

    if output_format not in {"json", "csv"}:
        raise ValueError("REACH_FILE_FORMAT must be either 'json' or 'csv'.")

    # Convert Output directory to Path object
    output_dir = Path(output_dir)

    # Set Start and End times for REACH data query
    end_time = Time.now() - TimeDelta(delay_seconds, format="sec")
    start_time = end_time - TimeDelta(window_seconds, format="sec")
    log.info(
        "Starting REACH download-to-file run",
        extra={
            "sensor_id": sensor_id,
            "descriptor": descriptor,
            "output_format": output_format,
            "start_time": format_udl_timestamp(start_time),
            "end_time": format_udl_timestamp(end_time),
        },
    )

    # Build chunked query windows and aggregate all records into one output artifact.
    dtlist = get_reach_datetimelist(
        start_time=start_time,
        end_time=end_time,
        sensor_id=sensor_id,
    )
    urls = get_reach_urllist(dtlist, sensor_id, descriptor)

    combined_obs: list[dict[str, Any]] = []
    chunk_results: dict[str, list[dict[str, Any]]] = {}

    if urls:
        max_workers = min(max_concurrent_requests, len(urls))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_dt = {}
            for i, (dt, url) in enumerate(urls.items()):
                log.info(
                    f"Queueing REACH file chunk {i + 1}/{len(urls)} from UDL at {url}"
                )
                future = executor.submit(fetch_reach_chunk, dt, url, auth_token)
                future_to_dt[future] = dt

            for future in as_completed(future_to_dt):
                dt, records = future.result()
                chunk_results[dt] = records
                log.info(
                    "Received REACH chunk",
                    extra={
                        "chunk_window": dt,
                        "chunk_record_count": len(records),
                    },
                )

    # Preserve chunk ordering in output regardless of completion order.
    for dt in dtlist:
        combined_obs.extend(chunk_results.get(dt, []))

    filename = build_reach_output_filename(
        sensor_id=sensor_id,
        start_time=start_time,
        end_time=end_time,
        output_format=output_format,
    )
    filepath = output_dir / filename
    write_reach_output(filepath, combined_obs, output_format)
    log.info(
        "REACH combined file written",
        extra={
            "filepath": filepath,
            "output_format": output_format,
            "total_record_count": len(combined_obs),
        },
    )
    return filepath
