import matplotlib.path as mpath
import numpy as np
import pytest

import swxsoc_reach.util.geom as geom_util


def test_read_contour_paths_filters_region_code(tmp_path):
    """read_contour_paths should return paths for every supported region code."""
    contour_file = tmp_path / "region_contour_paths.npz"

    contour_levels = np.array([-4, -3, -2, -1, 1, 2, 3, 4], dtype=int)
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
    np.savez_compressed(
        contour_file,
        contour_levels=contour_levels,
        vertices_by_segment=vertices_by_segment,
    )

    region_codes = [-4, -3, -2, -1, 1, 2, 3, 4]
    for code in region_codes:
        paths = geom_util.read_contour_paths(
            region_code=code, contour_file=contour_file
        )
        assert isinstance(paths, list)
        assert len(paths) > 0
        assert all(isinstance(path, mpath.Path) for path in paths)

    with pytest.raises(ValueError, match="Invalid region code"):
        geom_util.read_contour_paths(region_code=99, contour_file=contour_file)


def test_read_contour_paths_rejects_legacy_object_npz(tmp_path):
    """Object-array NPZ files should be rejected (no legacy pickle fallback)."""
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

    with pytest.raises(ValueError, match="Object arrays cannot be loaded"):
        geom_util.read_contour_paths(region_code=1, contour_file=contour_file)
