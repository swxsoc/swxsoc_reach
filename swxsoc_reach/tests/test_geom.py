import matplotlib.path as mpath
import numpy as np
import pytest

import swxsoc_reach.util.geom as geom_util
from swxsoc_reach.util.enums import Region


def test_load_region_contours_returns_all_region_codes(tmp_path):
    """load_region_contours should return paths for every supported region code."""
    contour_file = tmp_path / "region_contour_paths.npz"

    contour_levels = np.array(Region.contour_levels(), dtype=int)
    vertices_by_segment = np.array(
        [
            [[-1.0, -1.0], [-0.5, -1.0], [-0.5, -0.5], [-1.0, -1.0]],
            [[-2.0, -2.0], [-1.5, -2.0], [-1.5, -1.5], [-2.0, -2.0]],
            [[-3.0, -3.0], [-2.5, -3.0], [-2.5, -2.5], [-3.0, -3.0]],
            [[-4.0, -4.0], [-3.5, -4.0], [-3.5, -3.5], [-4.0, -4.0]],
            [[1.0, 1.0], [1.5, 1.0], [1.5, 1.5], [1.0, 1.0]],
            [[2.0, 2.0], [2.5, 2.0], [2.5, 2.5], [2.0, 2.0]],
            [[3.0, 3.0], [3.5, 3.0], [3.5, 3.5], [3.0, 3.0]],
            [[4.0, 4.0], [4.5, 4.0], [4.5, 4.5], [4.0, 4.0]],
        ],
        dtype=float,
    )

    all_vertices = vertices_by_segment.reshape(-1, 2)
    path_vertex_counts = np.full(contour_levels.size, 4, dtype=int)
    path_code_counts = np.full(contour_levels.size, 4, dtype=int)
    path_codes = np.array(
        [
            mpath.Path.MOVETO,
            mpath.Path.LINETO,
            mpath.Path.LINETO,
            mpath.Path.CLOSEPOLY,
        ],
        dtype=np.uint8,
    )
    all_codes = np.tile(path_codes, contour_levels.size)

    np.savez_compressed(
        contour_file,
        contour_levels=contour_levels,
        vertices=all_vertices,
        codes=all_codes,
        path_vertex_counts=path_vertex_counts,
        path_code_counts=path_code_counts,
    )

    paths_dict = geom_util.load_region_contours(contour_file=contour_file)
    assert set(paths_dict) == set(Region.contour_levels())
    assert all(isinstance(path, mpath.Path) for path in paths_dict.values())


def test_load_region_contours_rejects_legacy_object_npz(tmp_path):
    """Legacy NPZ schema should be rejected (no compatibility fallback)."""
    contour_file = tmp_path / "region_contour_paths_legacy.npz"
    contour_levels = np.array([1], dtype=int)
    vertices_by_segment = np.array(
        [np.array([[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]])],
        dtype=object,
    )
    np.savez_compressed(
        contour_file,
        contour_levels=contour_levels,
        vertices_by_segment=vertices_by_segment,
    )

    with pytest.raises(KeyError, match="vertices"):
        geom_util.load_region_contours(contour_file=contour_file)
