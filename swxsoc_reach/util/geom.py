"""Geometry utilities for REACH region operations."""

from __future__ import annotations

from pathlib import Path

import matplotlib.path as mpath
import numpy as np
import numpy.typing as npt

from swxsoc_reach import _data_directory

REGION_CODES = {
    -4: "Slot",
    -3: "Outer Zone",
    -2: "Polar Cap",
    -1: "SAA and Inner Zone",
    1: "SAA and Inner Zone",
    2: "Polar Cap",
    3: "Outer Zone",
    4: "Slot",
}


def read_contour_paths(
    region_code: int,
    contour_file: str | Path | None = None,
) -> list[mpath.Path]:
    """Read saved contour NPZ and return matplotlib paths for one region.

    Parameters
    ----------
    region_code : int
        Region code to filter by.
    contour_file : str | Path | None, optional
        Path to contour NPZ file. If None, uses package data file.

    Notes
    -----
    This function reads ``region_contour_paths.npz`` from the package data
    directory.

    Returns
    -------
    list[matplotlib.path.Path]
        Matplotlib path objects for the selected region code.
    """
    if region_code not in REGION_CODES.keys():
        valid_codes = list(REGION_CODES.keys())
        raise ValueError(
            f"Invalid region code: {region_code}. Must be one of {valid_codes}."
        )

    contour_path = (
        Path(contour_file)
        if contour_file is not None
        else _data_directory / "region_contour_paths.npz"
    )
    data = np.load(contour_path, allow_pickle=False)
    contour_levels = np.asarray(data["contour_levels"], dtype=int)
    vertices_by_segment = data["vertices_by_segment"]

    paths: list[mpath.Path] = []
    for code, verts in zip(contour_levels, vertices_by_segment, strict=False):
        if int(code) != int(region_code):
            continue
        segment_vertices = np.asarray(verts, dtype=float)
        if segment_vertices.shape[0] < 3:
            continue
        paths.append(mpath.Path(segment_vertices, closed=True))

    return paths


def point_in_region(
    lon: float | npt.NDArray,
    lat: float | npt.NDArray,
    region_code: int | None = None,
    csv_path: str | Path | None = None,
) -> int | npt.NDArray | None:
    """Return the region code(s) at given longitude/latitude point(s).

    Uses pre-loaded cached Shapely geometry for efficient repeated lookups.

    Parameters
    ----------
    lon : float | ndarray
        Longitude in degrees [-180, 180]. Can be scalar or array.
    lat : float | ndarray
        Latitude in degrees [-90, 90]. Can be scalar or array.
    region_code : int | None, optional
        If specified, only check if point(s) are within this region code.
        If None, return any matching region code.
    csv_path : str | Path | None, optional
        Path to the spline fit parameters CSV file. If None, uses default.

    Returns
    -------
    int | ndarray | None
        The region code (one of -4, -3, -2, -1, 1, 2, 3, 4) if the point(s)
        fall within a region, otherwise None.
        Returns array of codes for array input, scalar for scalar input.
    """
    geometry = _get_cached_geometry(csv_path)
    return geometry.get_region_code(lon, lat, region_code)
