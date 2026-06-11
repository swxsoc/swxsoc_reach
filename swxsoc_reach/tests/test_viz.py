import matplotlib.path as mpath
import numpy as np
import pytest
from cartopy import crs as ccrs

import swxsoc_reach.util.util as util
import swxsoc_reach.visualization.viz as viz
from swxsoc_reach.util.enums import Region


def test_plot_regions_writes_file(tmp_path, monkeypatch):
    """Test that plot_regions saves a plot using the loaded region arrays."""

    monkeypatch.setattr(
        util,
        "load_regions",
        lambda: (
            np.array([-120.0, -30.0, 45.0, 120.0]),
            np.array([-20.0, 65.0, 10.0, -5.0]),
            np.array([1, 2, 3, 4]),
        ),
    )

    output = tmp_path / "regions.png"
    result = viz.plot_regions(output, draw_coastlines=False)

    assert result == output
    assert output.exists()


def test_plot_regions_can_filter_to_saa(tmp_path, monkeypatch):
    """Test that plot_regions can render just the SAA region family."""

    monkeypatch.setattr(
        util,
        "load_regions",
        lambda: (
            np.array([-120.0, -30.0, 45.0, 120.0]),
            np.array([-20.0, 65.0, 10.0, -5.0]),
            np.array([1, 2, 3, 4]),
        ),
    )

    output = tmp_path / "regions_saa.png"
    result = viz.plot_regions(
        output,
        draw_coastlines=False,
        region_names=(Region.SAA.label,),
        title="SAA Region Map",
    )

    assert result == output
    assert output.exists()


def test_plot_region_contours_writes_file(tmp_path, monkeypatch):
    """Test that plot_region_contours saves a contour plot image."""

    monkeypatch.setattr(
        util,
        "load_regions",
        lambda: (
            np.array([-1.0, 0.0, -1.0, 0.0]),
            np.array([-1.0, -1.0, 0.0, 0.0]),
            np.array([1, 2, 3, 4]),
        ),
    )

    output = tmp_path / "region_contours.png"
    result = viz.plot_region_contours(output, draw_coastlines=False)

    assert result == output
    assert output.exists()


def test_plot_region_code_contours_on_geomap_returns_contour(monkeypatch):
    """Shared contour helper should return an axis and contour set."""
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(
        util,
        "load_regions",
        lambda: (
            np.array([-1.0, 0.0, -1.0, 0.0]),
            np.array([-1.0, -1.0, 0.0, 0.0]),
            np.array([1, 2, 3, 4]),
        ),
    )

    ax = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())
    out_ax, contour = viz.plot_region_code_contours_on_geomap(
        ax=ax,
        draw_coastlines=False,
        draw_gridlines=False,
        label_contours=False,
    )

    assert out_ax is ax
    assert contour is not None


def test_plot_geomap_without_contours_returns_none_contour(monkeypatch):
    """plot_geomap should allow disabling contour drawing."""
    pytest.importorskip("cartopy")
    import matplotlib.pyplot as plt

    monkeypatch.setattr(
        util,
        "load_regions",
        lambda: (
            np.array([-1.0, 0.0, -1.0, 0.0]),
            np.array([-1.0, -1.0, 0.0, 0.0]),
            np.array([1, 2, 3, 4]),
        ),
    )

    ax = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())
    out_ax, contour = viz.plot_geomap(
        ax=ax,
        draw_coastlines=False,
        draw_gridlines=False,
        draw_contours=False,
        label_contours=False,
    )

    assert out_ax is ax
    assert contour is None


def test_contour_image_to_path_returns_mpath_object_per_level():
    """Low-level contour extraction should return one matplotlib Path per level."""
    image = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
    )

    contour_paths = util.contour_image_to_path(image=image, contour_levels=[1.0])
    path = contour_paths[1.0]

    assert isinstance(path, mpath.Path)
    assert path.vertices.ndim == 2
    assert path.vertices.shape[1] == 2


def test_contour_image_to_path_returns_requested_levels():
    image = np.array(
        [
            [0.0, 1.0, 1.0, 0.0],
            [0.0, 1.0, 1.0, 0.0],
            [0.0, 0.0, 2.0, 2.0],
            [0.0, 0.0, 2.0, 2.0],
        ]
    )

    contour_paths = util.contour_image_to_path(image=image, contour_levels=[1.0, 2.0])

    assert set(contour_paths) == {1.0, 2.0}
    assert all(isinstance(path_obj, mpath.Path) for path_obj in contour_paths.values())
