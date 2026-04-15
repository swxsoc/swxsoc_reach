import json
import csv
import random
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal
from pathlib import Path
import requests
from astropy.time import Time, TimeDelta

from swxsoc_reach import log
from swxsoc_reach.util.util import TIME_FORMAT


class AdaptiveRateController:
    """Thread-safe AIMD rate controller for throttling HTTP requests.

    Uses Additive Increase / Multiplicative Decrease to dynamically
    adjust the permitted request rate based on server feedback.

    Parameters
    ----------
    initial_rate : float, optional
        Starting request rate in requests per second.
    additive_increase : float, optional
        Amount to add to the rate after each successful request.
    multiplicative_decrease : float, optional
        Factor to multiply the rate by after a rate-limit response.
    min_rate : float, optional
        Minimum permitted request rate.
    max_rate : float, optional
        Maximum permitted request rate.
    """

    def __init__(
        self,
        initial_rate: float = 5.0,
        additive_increase: float = 1.0,
        multiplicative_decrease: float = 0.5,
        min_rate: float = 5.0,
        max_rate: float = 25.0,
    ):
        self.rate = initial_rate
        self.additive_increase = additive_increase
        self.multiplicative_decrease = multiplicative_decrease
        self.min_rate = min_rate
        self.max_rate = max_rate
        self._lock = threading.Lock()
        self._last_request_time = 0.0

    def acquire(self) -> None:
        """Block until the next request is permitted under the current rate."""
        with self._lock:
            now = time.monotonic()
            delay = 1.0 / self.rate
            wait = self._last_request_time + delay - now
            if wait > 0:
                self._last_request_time = self._last_request_time + delay
            else:
                self._last_request_time = now

        if wait > 0:
            time.sleep(wait)

    def record_success(self) -> None:
        """Record a successful request and increase the rate additively."""
        with self._lock:
            self.rate = min(self.rate + self.additive_increase, self.max_rate)

    def record_rate_limit(self) -> None:
        """Record a rate-limit (429) response and decrease the rate."""
        with self._lock:
            self.rate = max(self.rate * self.multiplicative_decrease, self.min_rate)
            log.warning(
                "Rate limit hit, reducing request rate",
                extra={"new_rate": self.rate},
            )


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
    time_range = f"{start_time.strftime(TIME_FORMAT)}_{end_time.strftime(TIME_FORMAT)}"
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
    rate_controller: AdaptiveRateController | None = None,
    max_retries: int = 5,
) -> tuple[str, list[dict[str, Any]]]:
    """Fetch one UDL chunk and normalize the payload into a list of records.

    Includes retry logic with exponential back-off and jitter for HTTP 429
    responses. When a ``rate_controller`` is provided, it is used to
    throttle requests and receives success/failure feedback.

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
    rate_controller : AdaptiveRateController or None, optional
        Shared rate controller for AIMD throttling. If ``None``, no
        throttling or adaptive feedback is applied.
    max_retries : int, optional
        Maximum number of retry attempts after a 429 response.

    Returns
    -------
    tuple[str, list[dict[str, Any]]]
        The chunk window string and its records.

    Raises
    ------
    requests.HTTPError
        If UDL responds with an unsuccessful status code after all retries.
    """
    for attempt in range(max_retries + 1):
        # Wait for the rate controller to permit the next request.
        # This enforces a delay of 1/rate seconds between requests
        # across all threads sharing this controller.
        if rate_controller is not None:
            rate_controller.acquire()

        response = requests.get(
            url,
            headers={"Authorization": auth_token},
            timeout=timeout_seconds,
        )

        if response.status_code == 429:
            # Signal the rate controller to halve the request rate
            # (multiplicative decrease) so other threads also slow down.
            if rate_controller is not None:
                rate_controller.record_rate_limit()

            if attempt < max_retries:
                # Exponential back-off with random jitter to prevent
                # multiple threads from retrying in lockstep.
                backoff = (2**attempt) + random.uniform(0, 1)
                log.warning(
                    f"Chunk {dt} got 429, retrying in {backoff:.1f}s "
                    f"(attempt {attempt + 1}/{max_retries})"
                )
                time.sleep(backoff)
                continue
            else:
                log.error(f"Chunk {dt} failed after {max_retries} retries with 429")
                response.raise_for_status()

        response.raise_for_status()

        # Signal the rate controller to nudge the request rate upward
        # (additive increase) so throughput gradually recovers.
        if rate_controller is not None:
            rate_controller.record_success()

        obs_chunk = response.json()
        if isinstance(obs_chunk, list):
            normalized = obs_chunk
        elif obs_chunk:
            normalized = [obs_chunk]
        else:
            normalized = []

        return dt, normalized


def _write_chunk_file(
    chunk_path: Path,
    records: list[dict[str, Any]],
    output_format: Literal["json", "csv"],
) -> None:
    """Write a single chunk's records to a temporary file.

    Parameters
    ----------
    chunk_path : pathlib.Path
        Destination path for the chunk file.
    records : list[dict[str, Any]]
        Non-empty list of observation records to serialize.
    output_format : {'json', 'csv'}
        Serialization format.
    """
    if output_format == "json":
        with open(chunk_path, "w", encoding="utf-8") as chunk_f:
            json.dump(records, chunk_f)
    else:
        fieldnames = records[0].keys()
        with open(chunk_path, "w", newline="", encoding="utf-8") as chunk_f:
            writer = csv.DictWriter(chunk_f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)


def _concatenate_chunk_files(
    filepath: Path,
    dtlist: list[str],
    chunk_files: dict[str, Path],
    output_format: Literal["json", "csv"],
) -> None:
    """
    Stream-concatenate per-chunk temp files into one combined output file.

    Reads one temp file at a time so peak memory stays proportional to a
    single chunk rather than the full dataset.

    Parameters
    ----------
    filepath : pathlib.Path
        Destination path for the combined output file.
    dtlist : list[str]
        Chunk window identifiers in the desired output order.
    chunk_files : dict[str, pathlib.Path]
        Mapping of chunk window identifiers to their temp file paths.
        Only chunks that produced records are present.
    output_format : {'json', 'csv'}
        Serialization format of the output file.
    """
    if output_format == "json":
        with open(filepath, "w", encoding="utf-8") as out:
            out.write("[\n")
            first = True
            for dt in dtlist:
                if dt not in chunk_files:
                    continue
                # Each temp file is a JSON array like [{...}, {...}].
                # Strip the outer [] and splice the raw text directly
                # so we never parse records back into Python dicts.
                content = chunk_files[dt].read_text(encoding="utf-8").strip()
                inner = content[1:-1].strip()
                if not inner:
                    continue
                if not first:
                    out.write(",\n")
                out.write(inner)
                first = False
            out.write("\n]")
    else:
        header_written = False
        with open(filepath, "w", newline="", encoding="utf-8") as out:
            for dt in dtlist:
                if dt not in chunk_files:
                    continue
                with open(
                    chunk_files[dt], "r", newline="", encoding="utf-8"
                ) as chunk_f:
                    for line_num, line in enumerate(chunk_f):
                        if line_num == 0:
                            if not header_written:
                                out.write(line)
                                header_written = True
                            continue
                        out.write(line)


def download_UDL_reach_to_file(
    auth_token: str,
    sensor_id: str,
    descriptor: str,
    output_format: Literal["json", "csv"],
    delay_seconds: int,
    window_seconds: int,
    output_dir: Path | str,
    max_concurrent_requests: int = 4,
    initial_rate: float = 5.0,
    additive_increase: float = 1.0,
    multiplicative_decrease: float = 0.5,
    min_rate: float = 5.0,
    max_rate: float = 25.0,
) -> Path:
    """Download REACH data from UDL and write one combined output file.

    Each chunk is written to a temporary file as it arrives, keeping peak
    memory proportional to one chunk instead of the full dataset.  Temp
    files are concatenated in time order into the final output file and
    cleaned up automatically.

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
    initial_rate : float, optional
        Starting request rate in requests per second for the AIMD rate
        controller. Default is 5.0.
    additive_increase : float, optional
        Amount added to the rate after each successful request. Default is 1.0.
    multiplicative_decrease : float, optional
        Factor to multiply the rate by after a 429 response. Default is 0.5.
    min_rate : float, optional
        Minimum permitted request rate. Default is 5.0.
    max_rate : float, optional
        Maximum permitted request rate. Default is 25.0.

    Returns
    -------
    pathlib.Path
        Absolute or relative path (as provided) to the written output file.

    Raises
    ------
    ValueError
        If ``output_format`` is not one of ``'json'`` or ``'csv'``.
    ValueError
        If no records are returned for the requested time window.
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

    rate_controller = AdaptiveRateController(
        initial_rate=initial_rate,
        additive_increase=additive_increase,
        multiplicative_decrease=multiplicative_decrease,
        min_rate=min_rate,
        max_rate=max_rate,
    )

    # Each chunk is spooled to a temp file to avoid accumulating all records
    # in memory.  chunk_files maps dt -> Path for non-empty chunks.
    total_record_count = 0
    chunk_files: dict[str, Path] = {}

    if not urls:
        raise ValueError(
            f"No records returned for sensor '{sensor_id}' between "
            f"{format_udl_timestamp(start_time)} and "
            f"{format_udl_timestamp(end_time)}."
        )

    with tempfile.TemporaryDirectory(dir=output_dir) as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        max_workers = min(max_concurrent_requests, len(urls))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_chunk = {}
            total_chunks = len(urls)
            for request_index, (dt, url) in enumerate(urls.items(), start=1):
                log.info(f"Queueing Chunk {request_index} of {total_chunks}")
                future = executor.submit(
                    fetch_reach_chunk,
                    dt,
                    url,
                    auth_token,
                    rate_controller=rate_controller,
                )
                future_to_chunk[future] = (request_index, dt)

            for future in as_completed(future_to_chunk):
                request_index, _ = future_to_chunk[future]
                dt, records = future.result()
                record_count = len(records)
                total_record_count += record_count
                log.info(
                    f"Received Chunk {request_index} of {total_chunks}. "
                    f"Chunk window: {dt} with {record_count} records."
                )

                if records:
                    # Write chunk to a temp file and release the list
                    # from memory immediately.
                    chunk_path = tmp_dir_path / f"chunk_{request_index}.tmp"
                    _write_chunk_file(chunk_path, records, output_format)
                    chunk_files[dt] = chunk_path

        if total_record_count == 0:
            raise ValueError(
                f"No records returned for sensor '{sensor_id}' between "
                f"{format_udl_timestamp(start_time)} and "
                f"{format_udl_timestamp(end_time)}."
            )

        filename = build_reach_output_filename(
            sensor_id=sensor_id,
            start_time=start_time,
            end_time=end_time,
            output_format=output_format,
        )
        filepath = output_dir / filename
        _concatenate_chunk_files(filepath, dtlist, chunk_files, output_format)

    # TemporaryDirectory cleaned up here; final output is in output_dir.
    log.info(
        "REACH combined file written",
        extra={
            "filepath": filepath,
            "output_format": output_format,
            "total_record_count": total_record_count,
        },
    )
    return filepath
