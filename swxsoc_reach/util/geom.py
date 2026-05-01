"""Geometry utilities for REACH region operations."""

from __future__ import annotations

from os import path
from pathlib import Path

import matplotlib.path as mpath
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.ndimage import gaussian_filter

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


def contour_image_to_path(
    image: npt.ArrayLike,
    contour_level: float,
    x_values: npt.ArrayLike | None = None,
    y_values: npt.ArrayLike | None = None,
    blur_sigma: float = 0.0,
) -> mpath.Path | None:
    """Convert one contour level from an image into a matplotlib path.

    Parameters
    ----------
    image : array-like
        2-D array to contour.
    contour_level : float
        The value to contour at.
    x_values : array-like, optional
        1-D array of x coordinates (columns). Defaults to pixel indices.
    y_values : array-like, optional
        1-D array of y coordinates (rows). Defaults to pixel indices.
    blur_sigma : float, optional
        Standard deviation for Gaussian blur applied to the boolean mask
        before contouring. ``0.0`` (default) disables blurring.

    Returns
    -------
    matplotlib.path.Path or None
        Compound path of all contour segments, or ``None`` if none found.
    """
    image2d = np.asarray(image, dtype=float)
    if image2d.ndim != 2:
        raise ValueError("image must be a 2D array.")

    if x_values is None:
        x_arr = np.arange(image2d.shape[1], dtype=float)
    else:
        x_arr = np.asarray(x_values, dtype=float)

    if y_values is None:
        y_arr = np.arange(image2d.shape[0], dtype=float)
    else:
        y_arr = np.asarray(y_values, dtype=float)

    bool_image = (image2d == float(contour_level)).astype(float)

    if blur_sigma > 0.0:
        contour_data = gaussian_filter(bool_image, sigma=blur_sigma)
        contour_threshold = 0.5
    else:
        # Pad mask with zeros so contours touching domain edges become closed polygons.
        dx = float(np.median(np.diff(x_arr))) if x_arr.size > 1 else 1.0
        dy = float(np.median(np.diff(y_arr))) if y_arr.size > 1 else 1.0
        contour_data = np.pad(bool_image, 1, mode="constant", constant_values=0.0)
        x_arr = np.concatenate(([x_arr[0] - dx], x_arr, [x_arr[-1] + dx]))
        y_arr = np.concatenate(([y_arr[0] - dy], y_arr, [y_arr[-1] + dy]))
        contour_threshold = 0.5

    fig, ax = plt.subplots()
    contour = ax.contour(x_arr, y_arr, contour_data, levels=[contour_threshold])

    paths: list[mpath.Path] = []
    for segment in contour.allsegs[0]:
        vertices = np.asarray(segment, dtype=float)
        if vertices.shape[0] < 3:
            continue
        paths.append(mpath.Path(vertices, closed=True))

    plt.close(fig)

    if not paths:
        return None
    if len(paths) == 1:
        return paths[0]
    return mpath.Path.make_compound_path(*paths)


def read_contour_path(
    contour_file: str | Path | None = None,
) -> mpath.Path:
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

    contour_path = (
        Path(contour_file)
        if contour_file is not None
        else _data_directory / "region_contour_paths.npz"
    )
    data = np.load(contour_path, allow_pickle=False)
    vertices = np.asarray(data["vertices"], dtype=float)
    codes = data["codes"] if "codes" in data.files else None
    if codes is not None:
        codes = np.asarray(codes, dtype=np.uint8)
        if codes.size == 0:
            codes = None

    if codes is None:
        return mpath.Path(vertices, closed=True)
    return mpath.Path(vertices, codes=codes)


def load_region_contours() -> dict[int, mpath.Path]:
    """Load contour paths for all regions from the package data file."""
    paths_dict = {}

    for this_region in REGION_CODES.keys():
        this_region_str = str(this_region).replace("-", "neg").replace("+", "pos")
        input_path = _data_directory / f"contour_{this_region_str}.npz"
        this_path = read_contour_path(input_path)
        paths_dict[this_region] = this_path

    return paths_dict


def points_to_region_code(
    lon: float | npt.NDArray,
    lat: float | npt.NDArray,
    paths_dict: dict[int, mpath.Path],
) -> int | npt.NDArray | None:
    """Determine region code(s) for given longitude/latitude point(s) using contour paths."""
    lon_arr = np.atleast_1d(np.asarray(lon, dtype=float))
    lat_arr = np.atleast_1d(np.asarray(lat, dtype=float))
    if lon_arr.shape != lat_arr.shape:
        raise ValueError("lon and lat must have the same shape.")

    points = np.column_stack((lon_arr, lat_arr))
    region_codes = np.full(lon_arr.shape, fill_value=np.nan)

    def _contains_with_subpaths(path_obj: mpath.Path) -> np.ndarray:
        """Treat compound paths as union of subpaths for point containment."""
        codes = path_obj.codes
        if codes is None:
            return path_obj.contains_points(points)

        codes_arr = np.asarray(codes)
        move_indices = np.flatnonzero(codes_arr == mpath.Path.MOVETO)
        if move_indices.size <= 1:
            return path_obj.contains_points(points)

        vertices_arr = np.asarray(path_obj.vertices, dtype=float)
        inside_union = np.zeros(points.shape[0], dtype=bool)
        for idx, start in enumerate(move_indices):
            end = (
                move_indices[idx + 1]
                if idx + 1 < move_indices.size
                else len(vertices_arr)
            )
            sub_vertices = vertices_arr[start:end]
            sub_codes = codes_arr[start:end]
            if sub_vertices.shape[0] < 3:
                continue
            sub_path = mpath.Path(sub_vertices, codes=sub_codes)
            inside_union |= sub_path.contains_points(points)
        return inside_union

    for code, path_obj in paths_dict.items():
        if path_obj is None:
            continue
        inside = _contains_with_subpaths(path_obj)
        region_codes[inside] = code

    if np.isscalar(lon) and np.isscalar(lat):
        return region_codes[0]
    return region_codes
