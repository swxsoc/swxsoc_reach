"""
SunPy compatible Fido client for searching and retrieving REACH Dosimeter data.
"""

import urllib
from collections import OrderedDict
from html.parser import HTMLParser
from pathlib import Path
from typing import List
from urllib.parse import urljoin

from astropy.time import Time
from sunpy.net import attrs as a
from sunpy.net.attr import SimpleAttr
from sunpy.net.dataretriever import GenericClient, QueryResponse

from swxsoc_reach import log
from swxsoc_reach.util.enums import SensorId
from swxsoc_reach.util.util import parse_science_filename


class DataType(SimpleAttr):
    """
    Attribute for specifying the data type for the search.

    Attributes
    ----------
    value : str
        The data type value.
    """


class Vehicle(SimpleAttr):
    """
    Attribute for specifying the vehicle for the search.

    Attributes
    ----------
    value : str
        The vehicle value.
    """


class REACHClient(GenericClient):
    """
    Data source for searching and fetching REACH Data from SPDF File Servers.
    """

    baseurl = "https://spdf.gsfc.nasa.gov/pub/data/"

    @classmethod
    def register_values(cls):
        # Format the Vehicles List from Enum to SPDF-style
        vehicles = []
        for sensor in SensorId:
            vehicle_no = sensor.name.strip("REACH_")
            # Appent Tuple of (SPDF-Path, Sensor Name) for each vehicle
            vehicles.append((f"vid-{vehicle_no}_nc", sensor.name))
        # append "All REACH Satellites" option
        vehicles.append(("all_satellites", "All REACH Satellites"))

        adict = {
            a.Provider: [("spdf", "The Space Physics Data Facility.")],
            a.Source: [
                ("reach", "(Responsive Environmental Assessment Commercially Hosted)"),
            ],
            a.Instrument: [
                (
                    "Dosimeter",
                    "REACH Dosimeter",
                ),
            ],
            a.Level: [
                ("l1c", "Processed data in physical units."),
            ],
            Vehicle: vehicles,
            DataType: [
                ("prelim", "Preliminary Data Downloaded from UDL"),
            ],
        }
        return adict

    def search(self, *args, **kwargs) -> QueryResponse:
        """
        Query this client for a list of results.

        Parameters
        ----------
        \\*args: `tuple`
            `sunpy.net.attrs` objects representing the query.
        \\*\\*kwargs: `dict`
             Any extra keywords to refine the search.

        Returns
        -------
        A `QueryResponse` instance containing the query result.
        """
        matchdict = self._get_match_dict(*args, **kwargs)
        # Extract matchdict parameters
        instruments = matchdict.get("Instrument")
        levels = matchdict.get("Level")
        vehicles = matchdict.get("Vehicle")
        data_types = matchdict.get("DataType")
        start_time = matchdict.get("Start Time")
        end_time = matchdict.get("End Time")

        log.debug(
            "Extracted Search Parameters: %s",
            {
                "instruments": instruments,
                "levels": levels,
                "vehicles": vehicles,
                "data_types": data_types,
                "start_time": start_time,
                "end_time": end_time,
            },
        )

        # Get search paths with data_type
        search_paths = self._get_search_paths(
            instruments, levels, vehicles, data_types, start_time, end_time
        )
        log.debug(f"Search paths: {search_paths}")

        # Search each path
        all_files = []
        for path in search_paths:
            url = urljoin(self.baseurl, path)
            log.debug(f"Searching HTTP directory: {url}")
            files = self._crawl_directory(url)
            all_files.extend(files)

        log.debug(f"Total files found: {len(all_files)}")

        # Process, filter and return results
        metalist = []
        for file_url in all_files:
            log.debug(f"Processing file URL: {file_url}")
            info = parse_science_filename(file_url)

            # Filter Files by Time Range
            file_time = info.get("time")
            if file_time and start_time and end_time:
                if not (start_time <= file_time <= end_time):
                    log.debug(f"File {file_url} is outside the time range. Skipping.")
                    continue

            # Extract filename and extension using Path
            path_obj = Path(file_url)
            filename = path_obj.name
            file_extension = path_obj.suffix

            rowdict = OrderedDict()
            rowdict["Instrument"] = info.get("instrument", "unknown")
            rowdict["Mode"] = info.get("mode", "unknown")
            rowdict["Test"] = info.get("test", False)
            rowdict["Time"] = info.get("time", "unknown")
            rowdict["Level"] = info.get("level", "unknown")
            rowdict["Version"] = info.get("version", "unknown")
            rowdict["Descriptor"] = info.get("descriptor", "unknown")
            rowdict["File Name"] = filename
            rowdict["File Extension"] = file_extension
            rowdict["url"] = file_url  # Key
            metalist.append(rowdict)

        # pprint(f"Final metalist: {metalist}")
        return QueryResponse(metalist, client=self)

    def _get_search_paths(
        self,
        instruments: List[str] = None,
        levels: List[str] = None,
        vehicles: List[str] = None,
        data_types: List[str] = None,
        start_time: Time = None,
        end_time: Time = None,
    ):
        """Generate HTTP paths to search based on query parameters."""
        paths = []

        # Mission Name
        mission = "reach"

        # Get all relevant time paths between start_time and end_time, formatted as 'YYYY'
        time_paths = self._generate_time_paths(start_time, end_time)
        log.debug("Number of Time Paths Generated: %d", len(time_paths))

        # Combine all path components
        for instrument in instruments:
            for level in levels:
                for vehicle in vehicles:
                    if vehicle == "all_satellites":
                        for data_type in data_types:
                            for time_path in time_paths:
                                # For other levels, include data type in the path
                                # ex. /reach/dosimeter/l1c/all_satellites/prelim/2026
                                paths.append(
                                    f"{mission}/{instrument}/{level}/{vehicle}/{data_type}/{time_path}/"
                                )
                    else:
                        # For specific vehicles, we dont have any data_type in the path.
                        # ex. /reach/dosimeter/l1c/vid-136_nc/2019/
                        for time_path in time_paths:
                            paths.append(
                                f"{mission}/{instrument}/{level}/{vehicle}/{time_path}/"
                            )
        return paths

    @classmethod
    def _generate_time_paths(cls, start_time: Time, end_time: Time):
        """
        Generate all ``/year`` path components between start_time and end_time.

        REACH Files on SPDF are only organized by YEAR

        Parameters
        ----------
        start_time : astropy.time.Time
            Start time in ISO format (e.g., '2025-05-04')
        end_time : astropy.time.Time
            End time in ISO format (e.g., '2025-07-07')

        Returns
        -------
        list
            List of path strings in format 'YYYY'
        """
        # Iterate over every calendar year in the range, inclusive of both ends.
        start_year = start_time.datetime.year
        end_year = end_time.datetime.year
        time_paths = [str(year) for year in range(start_year, end_year + 1)]

        log.debug(
            f"Generated {len(time_paths)} time paths from {start_time} to {end_time}"
        )
        return time_paths

    def _crawl_directory(self, url):
        """Directory crawler using only standard library."""

        class LinkParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.links = []

            def handle_starttag(self, tag, attrs):
                if tag == "a":
                    for attr, value in attrs:
                        if attr == "href":
                            self.links.append(value)

        files = []
        try:
            with urllib.request.urlopen(url) as response:
                html = response.read().decode("utf-8")

            parser = LinkParser()
            parser.feed(html)

            for href in parser.links:
                # Skip parent directory links and query parameters
                if not href or href.startswith("?") or href == "../":
                    continue

                full_url = urljoin(url, href)

                # Don't crawl up: make sure we're still below our starting point
                if not full_url.startswith(self.baseurl) or len(full_url) < len(
                    self.baseurl
                ):
                    continue

                # Look for CDF Files or legacy NetCDF Files
                elif href.lower().endswith(".cdf") or href.lower().endswith(".nc"):
                    files.append(full_url)

            return files
        except Exception as e:
            log.debug(f"Error processing {url}: {e}")
            return []
