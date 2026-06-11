"""Geometry utilities for REACH region operations."""

from __future__ import annotations

from pathlib import Path

import matplotlib.path as mpath
import matplotlib.pyplot as plt
import numpy as np
import numpy.typing as npt
from scipy.ndimage import gaussian_filter

from swxsoc_reach import _data_directory
from swxsoc_reach.util.enums import Region

REGION_CODES = {
    code: region.label
    for region in Region.ordered()
    for code in (-region.code, region.code)
}


def contour_image_to_path(
    image: npt.ArrayLike,
    contour_levels: list[float],
    x_values: npt.ArrayLike | None = None,
    y_values: npt.ArrayLike | None = None,
    blur_sigma: float = 0.0,
) -> dict[float, mpath.Path | None]:
    """Convert one contour level from an image into a matplotlib path.

    Parameters
    ----------
    image : array-like
        2-D array to contour.
    contour_levels : list of float
        The values to contour at.
    x_values : array-like, optional
        1-D array of x coordinates (columns). Defaults to pixel indices.
    y_values : array-like, optional
        1-D array of y coordinates (rows). Defaults to pixel indices.
    blur_sigma : float, optional
        Standard deviation for Gaussian blur applied to the boolean mask
        before contouring. ``0.0`` (default) disables blurring.

    Returns
    -------
    dict[float, matplotlib.path.Path | None]
        Mapping from each requested contour level to a compound path of all
        contour segments for that level, or ``None`` if no contour is found.
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

    finite_values = np.unique(image2d[np.isfinite(image2d)])
    if finite_values.size == 0:
        return {float(level): None for level in contour_levels}

    finite_values = np.sort(finite_values.astype(float))
    if finite_values.size == 1:
        half_step = 0.5
        band_edges = np.array(
            [finite_values[0] - half_step, finite_values[0] + half_step],
            dtype=float,
        )
    else:
        midpoints = 0.5 * (finite_values[:-1] + finite_values[1:])
        lower_edge = finite_values[0] - 0.5 * (finite_values[1] - finite_values[0])
        upper_edge = finite_values[-1] + 0.5 * (finite_values[-1] - finite_values[-2])
        band_edges = np.concatenate(([lower_edge], midpoints, [upper_edge]))

    if blur_sigma > 0.0:
        contour_data = gaussian_filter(image2d, sigma=blur_sigma)
        contour_x = x_arr
        contour_y = y_arr
    else:
        # Pad the image so contours touching domain edges become closed polygons.
        # Use a fill value strictly below all band edges so padded cells are
        # unambiguously outside every band (avoids the 0.0 == midpoint(-1,+1) trap).
        fill_value = float(band_edges[0]) - 1.0
        dx = float(np.median(np.diff(x_arr))) if x_arr.size > 1 else 1.0
        dy = float(np.median(np.diff(y_arr))) if y_arr.size > 1 else 1.0
        contour_data = np.pad(image2d, 1, mode="constant", constant_values=fill_value)
        contour_x = np.concatenate(([x_arr[0] - dx], x_arr, [x_arr[-1] + dx]))
        contour_y = np.concatenate(([y_arr[0] - dy], y_arr, [y_arr[-1] + dy]))

    fig, ax = plt.subplots()
    contour = ax.contourf(contour_x, contour_y, contour_data, levels=band_edges)

    contour_paths: dict[float, mpath.Path | None] = {
        float(level): None for level in contour_levels
    }
    for contour_level, segments in zip(finite_values, contour.allsegs, strict=False):
        if float(contour_level) not in contour_paths:
            continue

        paths: list[mpath.Path] = []
        for segment in segments:
            vertices = np.asarray(segment, dtype=float)
            if vertices.shape[0] < 3:
                continue
            paths.append(mpath.Path(vertices, closed=True))

        if not paths:
            contour_paths[float(contour_level)] = None
        elif len(paths) == 1:
            contour_paths[float(contour_level)] = paths[0]
        else:
            contour_paths[float(contour_level)] = mpath.Path.make_compound_path(*paths)

    plt.close(fig)
    return contour_paths


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


def load_region_contours(
    contour_file: str | Path | None = None,
) -> dict[int, mpath.Path]:
    """Load contour paths for all regions from the combined package data file.

    Parameters
    ----------
    contour_file : str | Path | None, optional
        Path to the combined NPZ file written by the region-to-contours notebook.
        Defaults to ``region_contour_paths.npz`` in the package data directory.

    Returns
    -------
    dict[int, matplotlib.path.Path]
        Mapping from region code to a (possibly compound) matplotlib Path.
    """
    npz_path = (
        Path(contour_file)
        if contour_file is not None
        else _data_directory / "region_contour_paths.npz"
    )
    data = np.load(npz_path, allow_pickle=False)

    contour_levels = np.asarray(data["contour_levels"], dtype=int)
    all_vertices = np.asarray(data["vertices"], dtype=float)
    all_codes = (
        np.asarray(data["codes"], dtype=np.uint8)
        if "codes" in data.files
        else np.empty((0,), dtype=np.uint8)
    )
    path_vertex_counts = np.asarray(data["path_vertex_counts"], dtype=int)
    path_code_counts = np.asarray(data["path_code_counts"], dtype=int)

    paths_by_region: dict[int, list[mpath.Path]] = {}
    vert_offset = 0
    code_offset = 0

    for level, n_verts, n_codes in zip(
        contour_levels, path_vertex_counts, path_code_counts, strict=False
    ):
        verts = all_vertices[vert_offset : vert_offset + n_verts]
        vert_offset += n_verts

        if n_codes > 0:
            codes = all_codes[code_offset : code_offset + n_codes]
            code_offset += n_codes
            path = mpath.Path(verts, codes=codes)
        else:
            path = mpath.Path(verts, closed=True)

        region = int(level)
        paths_by_region.setdefault(region, []).append(path)

    result: dict[int, mpath.Path] = {}
    for region, region_paths in paths_by_region.items():
        if len(region_paths) == 1:
            result[region] = region_paths[0]
        else:
            result[region] = mpath.Path.make_compound_path(*region_paths)

    return result


def save_path_to_npz(
    contour_map: dict[int, mpath.Path | list[mpath.Path] | None],
    file_path: str | Path,
) -> Path:
    """Save region contour paths into a single compact NPZ file.

    Parameters
    ----------
    contour_map : dict[int, matplotlib.path.Path | list[matplotlib.path.Path] | None]
        Mapping from region code to either one path, many paths, or ``None``.
    file_path : str | Path
        Output NPZ file path.

    Returns
    -------
    pathlib.Path
        The output path that was written.
    """
    output_path = Path(file_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    contour_levels: list[int] = []
    vertex_arrays: list[npt.NDArray[np.float64]] = []
    code_arrays: list[npt.NDArray[np.uint8]] = []
    path_vertex_counts: list[int] = []
    path_code_counts: list[int] = []

    for contour_level, contour_value in sorted(contour_map.items()):
        if contour_value is None:
            continue

        contour_paths = (
            [contour_value]
            if isinstance(contour_value, mpath.Path)
            else list(contour_value)
        )

        for contour_path in contour_paths:
            vertices = np.asarray(contour_path.vertices, dtype=float)
            vertex_arrays.append(vertices)
            path_vertex_counts.append(int(vertices.shape[0]))
            contour_levels.append(int(contour_level))

            if contour_path.codes is None:
                path_code_counts.append(0)
                continue

            codes = np.asarray(contour_path.codes, dtype=np.uint8)
            code_arrays.append(codes)
            path_code_counts.append(int(codes.shape[0]))

    if not contour_levels:
        raise ValueError("At least one contour path is required.")

    np.savez_compressed(
        output_path,
        contour_levels=np.asarray(contour_levels, dtype=np.int32),
        vertices=np.concatenate(vertex_arrays, axis=0),
        codes=(
            np.concatenate(code_arrays, axis=0)
            if code_arrays
            else np.empty((0,), dtype=np.uint8)
        ),
        path_vertex_counts=np.asarray(path_vertex_counts, dtype=np.int32),
        path_code_counts=np.asarray(path_code_counts, dtype=np.int32),
    )

    return output_path


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
