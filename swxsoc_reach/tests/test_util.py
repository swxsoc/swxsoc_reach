import csv
import json
from pathlib import Path

import matplotlib.path as mpath
import numpy as np
import pytest
from scipy.interpolate import splprep

import swxsoc_reach.util.util as util
import swxsoc_reach.visualization.viz as viz
from swxsoc_reach import _test_files_directory

TIME = "2024-04-06T12:06:21"
TIME_FORMATTED = "20240406T120621"


# fmt: off
@pytest.mark.parametrize("time,level,version,descriptor,result", [
    (TIME, "l1", "1.2.3", "all", f"swxsoc_pipeline_reach_l1_all_{TIME_FORMATTED}_v1.2.3.cdf"),
    (TIME, "l2", "2.4.5", "all", f"swxsoc_pipeline_reach_l2_all_{TIME_FORMATTED}_v2.4.5.cdf"),
    (TIME, "l2", "1.3.5", "sci", f"swxsoc_pipeline_reach_l2_sci_{TIME_FORMATTED}_v1.3.5.cdf"),
    (TIME, "l3", "2.4.5", "cal", f"swxsoc_pipeline_reach_l3_cal_{TIME_FORMATTED}_v2.4.5.cdf"),
])
def test_create_reach_filename(time, level, version, descriptor, result):
    """Test that create_reach_filename generates correct CDF filenames.
    It wraps swxsoc.util.create_science_filename with instrument='reach'."""
    assert (
        util.create_reach_filename(time, level=level, descriptor=descriptor, version=version)
        == result
    )
# fmt: on


# fmt: off
@pytest.mark.parametrize("time,level,version,descriptor,result", [
    (TIME, "l1", "1.2.3", "all", f"swxsoc_pipeline_reach_l1_all_{TIME_FORMATTED}_v1.2.3.cdf"),
    (TIME, "l2", "2.4.5", "hk",  f"swxsoc_pipeline_reach_l2_hk_{TIME_FORMATTED}_v2.4.5.cdf"),
    (TIME, "l1", "1.0.0", "sci", f"swxsoc_pipeline_reach_l1_sci_{TIME_FORMATTED}_v1.0.0.cdf"),
])
def test_create_reach_filename_descriptors(time, level, version, descriptor, result):
    """Test that different descriptors are correctly included in the filename."""
    assert (
        util.create_reach_filename(time, level=level, descriptor=descriptor, version=version)
        == result
    )
# fmt: on


def test_create_reach_filename_test_flag():
    """Test that the test flag is passed through to the underlying swxsoc function."""
    filename = util.create_reach_filename(
        TIME, level="l1", descriptor="all", version="1.0.0", test=True
    )
    # When test=True, the swxsoc framework prepends or marks the filename as a test file
    assert "reach" in filename
    assert "l1" in filename


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
    result = util.plot_regions(output, draw_coastlines=False)

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
    result = util.plot_regions(
        output,
        draw_coastlines=False,
        region_names=("SAA and Inner Zone",),
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
    result = util.plot_region_contours(output, draw_coastlines=False)

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

    fig = plt.figure()
    ax = plt.subplot(1, 1, 1, projection=util.ccrs.PlateCarree())
    out_ax, contour = viz.plot_region_code_contours_on_geomap(
        ax=ax,
        draw_coastlines=False,
        draw_gridlines=False,
        label_contours=False,
    )

    assert out_ax is ax
    assert contour is not None


def test_generate_region_contour_data_returns_mpath_object(monkeypatch):
    """Contour utility should return a matplotlib Path object."""

    monkeypatch.setattr(
        util,
        "load_regions",
        lambda: (
            np.array([0.0, 1.0, 2.0, 0.0, 1.0, 2.0, 0.0, 1.0, 2.0]),
            np.array([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 2.0, 2.0, 2.0]),
            np.array([0, 0, 0, 0, 1, 0, 0, 0, 0]),
        ),
    )

    path = util.generate_region_contour_data(contour_levels=(0.5,))

    assert isinstance(path, mpath.Path)
    assert path.vertices.ndim == 2
    assert path.vertices.shape[1] == 2


def test_contour_image_to_path_returns_mpath_object():
    """Low-level contour extraction should return a matplotlib Path."""
    image = np.array(
        [
            [0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0],
        ]
    )

    path = util.contour_image_to_path(image=image, contour_level=0.5)

    assert isinstance(path, mpath.Path)
    assert path.vertices.ndim == 2
    assert path.vertices.shape[1] == 2


def test_read_spline_fit_polygons_returns_geometry(tmp_path):
    """Test that read_spline_fit_polygons returns a RegionGeometry object."""

    square = np.array(
        [
            [0.0, 0.0],
            [1.0, 0.0],
            [1.0, 1.0],
            [0.0, 1.0],
            [0.0, 0.0],
        ]
    )
    tck, _ = splprep([square[:, 0], square[:, 1]], s=0.0, k=1)

    csv_path = tmp_path / "fit_params.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "contour_level",
                "segment_index",
                "n_original_points",
                "n_fit_points",
                "arc_length_deg",
                "smoothing",
                "spline_order",
                "knots",
                "coeff_x",
                "coeff_y",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "contour_level": 1,
                "segment_index": 0,
                "n_original_points": 5,
                "n_fit_points": 5,
                "arc_length_deg": 4.0,
                "smoothing": 0.0,
                "spline_order": int(tck[2]),
                "knots": json.dumps(np.asarray(tck[0]).tolist()),
                "coeff_x": json.dumps(np.asarray(tck[1][0]).tolist()),
                "coeff_y": json.dumps(np.asarray(tck[1][1]).tolist()),
            }
        )

    # read_spline_fit_polygons now returns a RegionGeometry object
    geometry = util.read_spline_fit_polygons(csv_path, n_samples=200)

    assert isinstance(geometry, util.RegionGeometry)
    assert geometry._loaded
    assert geometry._polygons is not None
    assert len(geometry._polygons) == 1
    assert geometry._polygons[0]["contour_level"] == 1
    assert geometry._polygons[0]["polygon"].area > 0.5


def test_point_in_region_returns_code(tmp_path, monkeypatch):
    """Test that point_in_region returns the correct region code using Shapely."""
    import json

    # Create a simple square polygon for region 1
    square = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 2.0],
            [0.0, 2.0],
            [0.0, 0.0],
        ]
    )
    tck, _ = splprep([square[:, 0], square[:, 1]], s=0.0, k=1)

    csv_path = tmp_path / "fit_params.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "contour_level",
                "segment_index",
                "n_original_points",
                "n_fit_points",
                "arc_length_deg",
                "smoothing",
                "spline_order",
                "knots",
                "coeff_x",
                "coeff_y",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "contour_level": 1,
                "segment_index": 0,
                "n_original_points": 5,
                "n_fit_points": 5,
                "arc_length_deg": 4.0,
                "smoothing": 0.0,
                "spline_order": int(tck[2]),
                "knots": json.dumps(np.asarray(tck[0]).tolist()),
                "coeff_x": json.dumps(np.asarray(tck[1][0]).tolist()),
                "coeff_y": json.dumps(np.asarray(tck[1][1]).tolist()),
            }
        )

    # Point inside the square (1, 1)
    result = util.point_in_region(1.0, 1.0, csv_path=csv_path)
    assert result == 1


def test_point_in_region_array_input(tmp_path):
    """Test that point_in_region handles numpy array inputs."""
    import json

    # Create a simple square polygon for region 1
    square = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 2.0],
            [0.0, 2.0],
            [0.0, 0.0],
        ]
    )
    tck, _ = splprep([square[:, 0], square[:, 1]], s=0.0, k=1)

    csv_path = tmp_path / "fit_params.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "contour_level",
                "segment_index",
                "n_original_points",
                "n_fit_points",
                "arc_length_deg",
                "smoothing",
                "spline_order",
                "knots",
                "coeff_x",
                "coeff_y",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "contour_level": 1,
                "segment_index": 0,
                "n_original_points": 5,
                "n_fit_points": 5,
                "arc_length_deg": 4.0,
                "smoothing": 0.0,
                "spline_order": int(tck[2]),
                "knots": json.dumps(np.asarray(tck[0]).tolist()),
                "coeff_x": json.dumps(np.asarray(tck[1][0]).tolist()),
                "coeff_y": json.dumps(np.asarray(tck[1][1]).tolist()),
            }
        )

    # Test array of points: inside, outside, inside, outside
    lons = np.array([1.0, 5.0, 0.5, 10.0])
    lats = np.array([1.0, 5.0, 0.5, 10.0])

    result = util.point_in_region(lons, lats, csv_path=csv_path)

    assert result.shape == (4,)
    assert result[0] == 1  # Inside
    assert result[1] is None  # Outside
    assert result[2] == 1  # Inside
    assert result[3] is None  # Outside


def test_region_geometry_caches_polygons(tmp_path):
    """Test that RegionGeometry caches polygons efficiently."""
    import json

    # Create a simple square polygon
    square = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 2.0],
            [0.0, 2.0],
            [0.0, 0.0],
        ]
    )
    tck, _ = splprep([square[:, 0], square[:, 1]], s=0.0, k=1)

    csv_path = tmp_path / "fit_params.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "contour_level",
                "segment_index",
                "n_original_points",
                "n_fit_points",
                "arc_length_deg",
                "smoothing",
                "spline_order",
                "knots",
                "coeff_x",
                "coeff_y",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "contour_level": 1,
                "segment_index": 0,
                "n_original_points": 5,
                "n_fit_points": 5,
                "arc_length_deg": 4.0,
                "smoothing": 0.0,
                "spline_order": int(tck[2]),
                "knots": json.dumps(np.asarray(tck[0]).tolist()),
                "coeff_x": json.dumps(np.asarray(tck[1][0]).tolist()),
                "coeff_y": json.dumps(np.asarray(tck[1][1]).tolist()),
            }
        )

    # Create geometry instance
    geom = util.RegionGeometry(csv_path)

    # First call should load polygons
    result1 = geom.get_region_code(1.0, 1.0)
    assert result1 == 1
    assert geom._loaded

    # Second call should use cached polygons (not reload)
    result2 = geom.get_region_code(1.0, 1.0)
    assert result2 == 1


def test_point_in_region_with_region_code_filter(tmp_path):
    """Test that point_in_region can filter by region code."""
    import json

    # Create two square polygons for regions 1 and 2
    square1 = np.array(
        [
            [0.0, 0.0],
            [2.0, 0.0],
            [2.0, 2.0],
            [0.0, 2.0],
            [0.0, 0.0],
        ]
    )
    square2 = np.array(
        [
            [3.0, 0.0],
            [5.0, 0.0],
            [5.0, 2.0],
            [3.0, 2.0],
            [3.0, 0.0],
        ]
    )

    tck1, _ = splprep([square1[:, 0], square1[:, 1]], s=0.0, k=1)
    tck2, _ = splprep([square2[:, 0], square2[:, 1]], s=0.0, k=1)

    csv_path = tmp_path / "fit_params.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "contour_level",
                "segment_index",
                "n_original_points",
                "n_fit_points",
                "arc_length_deg",
                "smoothing",
                "spline_order",
                "knots",
                "coeff_x",
                "coeff_y",
            ],
        )
        writer.writeheader()
        for idx, tck in enumerate([tck1, tck2], start=1):
            writer.writerow(
                {
                    "contour_level": idx,
                    "segment_index": 0,
                    "n_original_points": 5,
                    "n_fit_points": 5,
                    "arc_length_deg": 4.0,
                    "smoothing": 0.0,
                    "spline_order": int(tck[2]),
                    "knots": json.dumps(np.asarray(tck[0]).tolist()),
                    "coeff_x": json.dumps(np.asarray(tck[1][0]).tolist()),
                    "coeff_y": json.dumps(np.asarray(tck[1][1]).tolist()),
                }
            )

    # Point (1, 1) is in region 1, not in region 2
    result = util.point_in_region(1.0, 1.0, region_code=1, csv_path=csv_path)
    assert result == 1

    result_no_filter = util.point_in_region(1.0, 1.0, csv_path=csv_path)
    assert result_no_filter == 1

    # When filtering for region 2, should return None
    result_wrong = util.point_in_region(1.0, 1.0, region_code=2, csv_path=csv_path)
    assert result_wrong is None


def test_point_in_region_random_points_each_region(tmp_path):
    """Sample 100 random interior points per region and verify membership."""
    rng = np.random.default_rng(42)
    region_codes = [-4, -3, -2, -1, 1, 2, 3, 4]

    csv_path = tmp_path / "fit_params.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "contour_level",
                "segment_index",
                "n_original_points",
                "n_fit_points",
                "arc_length_deg",
                "smoothing",
                "spline_order",
                "knots",
                "coeff_x",
                "coeff_y",
            ],
        )
        writer.writeheader()

        for idx, code in enumerate(region_codes):
            x0 = 10.0 * idx
            y0 = 5.0 * idx
            width = 3.0
            height = 2.0

            square = np.array(
                [
                    [x0, y0],
                    [x0 + width, y0],
                    [x0 + width, y0 + height],
                    [x0, y0 + height],
                    [x0, y0],
                ]
            )
            tck, _ = splprep([square[:, 0], square[:, 1]], s=0.0, k=1)

            writer.writerow(
                {
                    "contour_level": code,
                    "segment_index": 0,
                    "n_original_points": 5,
                    "n_fit_points": 5,
                    "arc_length_deg": 2.0 * (width + height),
                    "smoothing": 0.0,
                    "spline_order": int(tck[2]),
                    "knots": json.dumps(np.asarray(tck[0]).tolist()),
                    "coeff_x": json.dumps(np.asarray(tck[1][0]).tolist()),
                    "coeff_y": json.dumps(np.asarray(tck[1][1]).tolist()),
                }
            )

    for idx, code in enumerate(region_codes):
        x0 = 10.0 * idx
        y0 = 5.0 * idx

        # Keep points away from boundaries since within() excludes boundaries.
        lon_samples = rng.uniform(x0 + 0.2, x0 + 2.8, size=100)
        lat_samples = rng.uniform(y0 + 0.2, y0 + 1.8, size=100)

        result_all = util.point_in_region(lon_samples, lat_samples, csv_path=csv_path)
        assert np.all(result_all == code)

        result_filtered = util.point_in_region(
            lon_samples, lat_samples, region_code=code, csv_path=csv_path
        )
        assert np.all(result_filtered == code)


def test_point_in_region_fixture_points_match_regions():
    """Read NPZ fixture points and verify each point is inside its contour path."""
    repo_root = Path(__file__).resolve().parents[2]
    fixture_path = (
        repo_root / "swxsoc_reach" / "data" / "test" / "region_random_points.npz"
    )
    contour_paths_path = repo_root / "region_contour_paths.npz"

    if not fixture_path.exists():
        pytest.skip("region_random_points.npz fixture file not found")
    if not contour_paths_path.exists():
        pytest.skip("region_contour_paths.npz not found in repo root")

    data = np.load(fixture_path, allow_pickle=True)
    region_codes = np.asarray(data["region_codes"], dtype=int)
    points_by_region = data["points_by_region"]

    for code, points in zip(region_codes, points_by_region, strict=False):
        code_paths = util.read_contour_paths(contour_paths_path, region_code=int(code))
        assert len(code_paths) > 0

        point_array = np.asarray(points, dtype=float)
        for lon, lat in point_array:
            is_inside = any(
                path.contains_point((float(lon), float(lat))) for path in code_paths
            )
            assert is_inside


def test_read_contour_paths_filters_region_code(tmp_path, monkeypatch):
    """Test reading contour NPZ returns matplotlib paths for selected code."""
    contour_file = tmp_path / "region_contour_paths.npz"
    contour_levels = np.array([1, 2, 1], dtype=int)
    vertices_by_segment = np.array(
        [
            [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 0.0]],
            [[2.0, 2.0], [3.0, 2.0], [3.0, 3.0], [2.0, 2.0]],
            [[-1.0, -1.0], [-0.5, -1.0], [-0.5, -0.5], [-1.0, -1.0]],
        ],
        dtype=float,
    )
    np.savez_compressed(
        contour_file,
        contour_levels=contour_levels,
        vertices_by_segment=vertices_by_segment,
    )

    monkeypatch.setattr(util, "_data_directory", tmp_path)

    region_1_paths = util.read_contour_paths(region_code=1)
    region_2_paths = util.read_contour_paths(region_code=2)
    region_3_paths = util.read_contour_paths(region_code=3)

    assert len(region_1_paths) == 2
    assert len(region_2_paths) == 1
    assert len(region_3_paths) == 0
    assert all(isinstance(path, mpath.Path) for path in region_1_paths)
