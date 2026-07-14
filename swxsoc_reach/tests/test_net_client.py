"""Tests for the REACH SPDF Fido client (:class:`swxsoc_reach.net.REACHClient`)."""

import os
import tempfile
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest
from astropy.time import Time
from sunpy.net import Fido
from sunpy.net import attrs as a

from swxsoc_reach.net.client import DataType, REACHClient, Vehicle


@pytest.fixture
def http_file_server():
    """
    Serve a REACH SPDF-style directory tree over a temporary local HTTP server.

    The layout mirrors the public SPDF archive::

        reach/dosimeter/l1c/all_satellites/prelim/<YYYY>/   (multi-satellite CDFs)
        reach/dosimeter/l1c/vid-<NNN>_nc/<YYYY>/            (single-satellite CDFs)

    Both modern ``.cdf`` files and legacy ``.nc`` files are included so the
    crawler's file-extension handling is exercised.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        base_path = "reach/dosimeter/l1c"

        # all_satellites CDFs (path includes the ``prelim`` data type)
        all_sats = {
            "2025": [
                "reach_all_l1c_prelim_20250501T000000_v1.0.0.cdf",
                "reach_all_l1c_prelim_20250503T000000_v1.0.0.cdf",
            ],
            "2026": [
                "reach_all_l1c_prelim_20260707T000000_v1.0.0.cdf",
            ],
        }
        for year, filenames in all_sats.items():
            folder = os.path.join(tmpdir, base_path, "all_satellites", "prelim", year)
            os.makedirs(folder, exist_ok=True)
            for filename in filenames:
                with open(os.path.join(folder, filename), "w") as f:
                    f.write(f"CDF data for {filename}")

        # Legacy NetCDF file served alongside the modern all_satellites CDFs
        legacy_folder = os.path.join(
            tmpdir, base_path, "all_satellites", "prelim", "2018"
        )
        os.makedirs(legacy_folder, exist_ok=True)
        legacy_file = "reach_all_l1c_prelim_20180501T000000_v1.0.0.nc"
        with open(os.path.join(legacy_folder, legacy_file), "w") as f:
            f.write("Legacy NetCDF data")

        # Single-satellite CDF (path does NOT include a data type folder)
        vehicle_folder = os.path.join(tmpdir, base_path, "vid-136_nc", "2019")
        os.makedirs(vehicle_folder, exist_ok=True)
        vehicle_file = "reach_136_l1c_prelim_20190501T000000_v1.0.0.cdf"
        with open(os.path.join(vehicle_folder, vehicle_file), "w") as f:
            f.write("CDF data for a single REACH satellite")

        # Start a quiet HTTP server rooted at the temporary directory
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

        server = HTTPServer(("localhost", 0), QuietHandler)
        port = server.server_port
        thread = threading.Thread(target=server.serve_forever)
        cwd = os.getcwd()
        os.chdir(tmpdir)
        thread.start()
        try:
            yield f"http://localhost:{port}/"
        finally:
            server.shutdown()
            thread.join()
            os.chdir(cwd)


def test_register_values():
    """The client registers the attributes needed to route Fido queries."""
    adict = REACHClient.register_values()

    sources = [value for value, _ in adict[a.Source]]
    assert "reach" in sources

    instruments = [value for value, _ in adict[a.Instrument]]
    assert "Dosimeter" in instruments

    levels = [value for value, _ in adict[a.Level]]
    assert "l1c" in levels

    data_types = [value for value, _ in adict[DataType]]
    assert "prelim" in data_types

    vehicles = [value for value, _ in adict[Vehicle]]
    assert "all_satellites" in vehicles
    assert "vid-136_nc" in vehicles


@pytest.mark.parametrize(
    "vehicles,data_types,start,end,expected_paths",
    [
        # all_satellites includes the data type folder in the path
        (
            ["all_satellites"],
            ["prelim"],
            "2025-05-01",
            "2025-05-05",
            ["reach/dosimeter/l1c/all_satellites/prelim/2025/"],
        ),
        # a specific vehicle omits the data type folder entirely
        (
            ["vid-136_nc"],
            ["prelim"],
            "2019-05-01",
            "2019-05-05",
            ["reach/dosimeter/l1c/vid-136_nc/2019/"],
        ),
        # REACH is organized by YEAR, so a multi-year span fans out per year
        (
            ["all_satellites"],
            ["prelim"],
            "2018-06-01",
            "2020-02-01",
            [
                "reach/dosimeter/l1c/all_satellites/prelim/2018/",
                "reach/dosimeter/l1c/all_satellites/prelim/2019/",
                "reach/dosimeter/l1c/all_satellites/prelim/2020/",
            ],
        ),
    ],
)
def test_get_search_paths(vehicles, data_types, start, end, expected_paths):
    client = REACHClient()
    paths = client._get_search_paths(
        instruments=["dosimeter"],
        levels=["l1c"],
        vehicles=vehicles,
        data_types=data_types,
        start_time=Time(start),
        end_time=Time(end),
    )
    assert sorted(paths) == sorted(expected_paths)


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("2025-05-01", "2025-05-05", ["2025"]),
        ("2018-01-01", "2020-12-31", ["2018", "2019", "2020"]),
    ],
)
def test_generate_time_paths(start, end, expected):
    """Time paths are generated at YEAR granularity for REACH."""
    paths = REACHClient._generate_time_paths(Time(start), Time(end))
    assert paths == expected


def test_fido_search_all_satellites(http_file_server, monkeypatch):
    """Searching all satellites returns the CDFs within the time range."""
    monkeypatch.setattr("swxsoc_reach.net.client.REACHClient.baseurl", http_file_server)

    result = Fido.search(
        a.Time("2025-05-01", "2025-05-05")
        & a.Source.reach
        & a.Instrument.dosimeter
        & Vehicle.all_satellites
    )
    reach_results = result["reach"]
    assert len(reach_results) == 2
    assert all(level == "l1c" for level in reach_results["Level"])
    assert all(desc == "prelim" for desc in reach_results["Descriptor"])
    assert all(ext == ".cdf" for ext in reach_results["File Extension"])


def test_fido_search_time_filtering(http_file_server, monkeypatch):
    """Files outside the requested time range are filtered out."""
    monkeypatch.setattr("swxsoc_reach.net.client.REACHClient.baseurl", http_file_server)

    result = Fido.search(
        a.Time("2025-05-01", "2025-05-02")
        & a.Source.reach
        & a.Instrument.dosimeter
        & Vehicle.all_satellites
    )
    reach_results = result["reach"]
    assert len(reach_results) == 1
    assert reach_results["File Name"][0] == (
        "reach_all_l1c_prelim_20250501T000000_v1.0.0.cdf"
    )


def test_fido_search_specific_vehicle(http_file_server, monkeypatch):
    """A specific vehicle searches the vid-<NNN>_nc path (no data type folder)."""
    monkeypatch.setattr("swxsoc_reach.net.client.REACHClient.baseurl", http_file_server)

    result = Fido.search(
        a.Time("2019-05-01", "2019-05-05")
        & a.Source.reach
        & a.Instrument.dosimeter
        & Vehicle.vid_136_nc
    )
    reach_results = result["reach"]
    assert len(reach_results) == 1
    assert reach_results["File Name"][0] == (
        "reach_136_l1c_prelim_20190501T000000_v1.0.0.cdf"
    )


def test_fido_search_legacy_netcdf(http_file_server, monkeypatch):
    """Legacy ``.nc`` files are discovered when no vehicle is specified."""
    monkeypatch.setattr("swxsoc_reach.net.client.REACHClient.baseurl", http_file_server)

    result = Fido.search(
        a.Time("2018-05-01", "2018-05-05") & a.Source.reach & a.Instrument.dosimeter
    )
    reach_results = result["reach"]
    assert len(reach_results) == 1
    assert reach_results["File Extension"][0] == ".nc"
