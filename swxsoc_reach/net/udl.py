import json
import csv
from typing import Any, Dict
from pathlib import Path
import requests
from astropy.time import Time, TimeDelta

from swxsoc_reach import log


def format_udl_timestamp(value: Time) -> str:
    """Format an Astropy Time value for UDL query parameters."""
    return f"{value.isot.split('.')[0]}.000Z"


def get_reach_datetimelist(
    start_time: Time, end_time: Time, sensor_id: str
) -> list[str]:
    """Split a query range into UDL-safe chunks for REACH requests."""
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
) -> Dict[str, str]:
    """Build UDL URLs for each REACH time chunk."""
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
    output_format: str,
) -> str:
    """Build deterministic filename for one combined REACH output artifact."""
    sensor_prefix = "REACH-ALL" if sensor_id.upper() == "ALL" else sensor_id
    time_range = (
        f"{start_time.strftime('%Y%m%dT%H%M%S')}_{end_time.strftime('%Y%m%dT%H%M%S')}"
    )
    return f"{sensor_prefix}_{time_range}.{output_format}"


def write_reach_output(
    filepath: Path, obs: list[Dict[str, Any]], output_format: str
) -> None:
    """Write REACH payload to JSON or CSV file."""
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


def download_UDL_reach_to_file(
    auth_token: str,
    sensor_id: str,
    descriptor: str,
    output_format: str,
    delay_seconds: int,
    window_seconds: int,
    output_dir: Path,
) -> Path:
    """
    Download REACH data from UDL and save to file.
    """

    if output_format not in {"json", "csv"}:
        raise ValueError("REACH_FILE_FORMAT must be either 'json' or 'csv'.")

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

    combined_obs: list[Dict[str, Any]] = []
    chunk_count = 0
    for dt, url in urls.items():
        log.info(f"Requesting REACH file chunk from UDL at {url}")

        # Curl the UDL endpoint for this chunk
        response = requests.get(
            url,
            headers={"Authorization": auth_token},
            timeout=60,
        )
        response.raise_for_status()

        # Add chunk data to combined list
        obs_chunk = response.json()
        if isinstance(obs_chunk, list):
            combined_obs.extend(obs_chunk)
        elif obs_chunk:
            combined_obs.append(obs_chunk)
        chunk_count += 1
        log.info(
            "Received REACH chunk",
            extra={
                "chunk_window": dt,
                "chunk_record_count": len(obs_chunk)
                if isinstance(obs_chunk, list)
                else 1,
            },
        )

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
