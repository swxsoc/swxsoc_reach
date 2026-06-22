"""A module for visualizing REACH data, including plotting functions and utilities."""

import warnings
from pathlib import Path
from typing import Any, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from cartopy import crs as ccrs
from matplotlib.path import Path as MplPath
from swxsoc.swxdata import SWXData

from swxsoc_reach import log
from swxsoc_reach.util.enums import Region
from swxsoc_reach.util.geom import load_region_contours
from swxsoc_reach.util.util import load_regions

# REACH dose data routinely contains zeros / non-positive values; log10 of
# these is mathematically undefined but expected, so silence the resulting
# RuntimeWarnings for this module only.
warnings.filterwarnings(
    "ignore",
    message="divide by zero encountered in log10",
    category=RuntimeWarning,
    module=__name__,
)
warnings.filterwarnings(
    "ignore",
    message="invalid value encountered in log10",
    category=RuntimeWarning,
    module=__name__,
)


def plot_regions(
    fileout: str | Path,
    show: bool = False,
    title: str = "REACH Region Map",
    draw_coastlines: bool = True,
    region_names: tuple[str, ...] | None = None,
) -> Path | None:
    """
    Plot the region map returned by :func:`load_regions` and save it.

    Parameters
    ----------
    fileout : str or Path
        Output file path where the plot will be saved.
    show : bool, optional
        If True, display the plot. Default is False.
    title : str, optional
        Title for the plot. Default is "REACH Region Map".
    draw_coastlines : bool, optional
        If True, draw coastlines on the map. Default is True.
    region_names : tuple of str or None, optional
        Names of specific regions to plot. If None, all regions are plotted. Default is None.

    Returns
    -------
    Path or None
        Path to the saved output file, or None if no data was available.
    """
    lookuplon, lookuplat, glook = load_regions()
    if lookuplon.size == 0:
        return None

    region_specs = [
        (region.label, region.signed_codes, region.color) for region in Region.ordered()
    ]
    selected_names = None
    if region_names is not None:
        selected_names = {name.casefold() for name in region_names}

    fig = plt.figure(figsize=(11.69, 8.27))
    ax: Any = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax.set_global()
    if draw_coastlines:
        ax.coastlines()

    ax.gridlines(
        draw_labels=True,
        xlocs=np.arange(-180, 181, 30),
        ylocs=np.arange(-90, 91, 10),
        color="gray",
        linestyle="--",
    )

    for label, codes, color in region_specs:
        if selected_names is not None and label.casefold() not in selected_names:
            continue
        mask = np.isin(glook, codes)
        if np.any(mask):
            ax.scatter(
                lookuplon[mask],
                lookuplat[mask],
                s=8,
                c=color,
                label=label,
                linewidths=0,
                alpha=0.85,
                transform=ccrs.PlateCarree(),
            )

    ax.set_title(title, fontdict={"fontsize": 15})
    ax.legend(loc="lower left", frameon=True)

    output_path = Path(fileout)
    fig.savefig(output_path, orientation="landscape", bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)
    return output_path


def plot_region_contours(
    fileout: str | Path,
    show: bool = False,
    title: str = "REACH Region Code Contours",
    draw_coastlines: bool = True,
) -> Path | None:
    """
    Plot labeled line contours for the integer region-code grid.

    Parameters
    ----------
    fileout : str or Path
        Output file path where the plot will be saved.
    show : bool, optional
        If True, display the plot. Default is False.
    title : str, optional
        Title for the plot. Default is "REACH Region Code Contours".
    draw_coastlines : bool, optional
        If True, draw coastlines on the map. Default is True.

    Returns
    -------
    Path or None
        Path to the saved output file, or None if no contours were created.
    """

    fig = plt.figure(figsize=(11.69, 8.27))
    ax: Any = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())
    ax, contour = plot_geomap(
        ax=ax,
        draw_coastlines=draw_coastlines,
        draw_gridlines=True,
        draw_contours=True,
        label_contours=True,
    )

    if contour is None:
        plt.close(fig)
        return None

    ax.set_title(title, fontdict={"fontsize": 15})

    output_path = Path(fileout)
    fig.savefig(output_path, orientation="landscape", bbox_inches="tight")

    if show:
        plt.show()

    plt.close(fig)
    return output_path


def plot_geomap(
    ax: Any | None = None,
    *,
    draw_coastlines: bool = False,
    draw_gridlines: bool = False,
    draw_contours: bool = True,
    contour_levels: Sequence[float] | None = None,
    contour_colors: Sequence[str] | None = None,
    linewidths: float = 1.2,
    label_contours: bool = False,
):
    """Draw a global PlateCarree geomap base and optionally region contours."""
    contour_paths = load_region_contours()

    if contour_levels is None:
        contour_levels = Region.contour_levels()
    if contour_colors is None:
        contour_colors = Region.contour_colors()

    if ax is None:
        plt.figure(figsize=(11.69, 8.27))
        ax = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree())

    ax.set_global()
    if draw_coastlines:
        ax.coastlines()
    if draw_gridlines:
        ax.gridlines(
            draw_labels=True,
            xlocs=np.arange(-180, 181, 30),
            ylocs=np.arange(-90, 91, 10),
            color="gray",
            linestyle="--",
        )

    contour = None
    if draw_contours:
        contour_lines = []
        for level, color in zip(contour_levels, contour_colors, strict=False):
            path_obj = contour_paths.get(int(level))
            if path_obj is None:
                continue

            vertices = np.asarray(path_obj.vertices, dtype=float)
            codes = path_obj.codes

            if codes is None:
                finite_vertices = vertices[np.all(np.isfinite(vertices), axis=1)]
                if finite_vertices.shape[0] >= 2:
                    line = ax.plot(
                        finite_vertices[:, 0],
                        finite_vertices[:, 1],
                        color=color,
                        linewidth=linewidths,
                        transform=ccrs.PlateCarree(),
                    )
                    contour_lines.extend(line)
            else:
                segment_vertices: list[np.ndarray] = []
                for vertex, code in zip(vertices, codes, strict=False):
                    if code == MplPath.MOVETO:
                        if len(segment_vertices) >= 2:
                            seg = np.asarray(segment_vertices, dtype=float)
                            line = ax.plot(
                                seg[:, 0],
                                seg[:, 1],
                                color=color,
                                linewidth=linewidths,
                                transform=ccrs.PlateCarree(),
                            )
                            contour_lines.extend(line)
                        segment_vertices = [vertex]
                    elif code == MplPath.CLOSEPOLY:
                        if len(segment_vertices) >= 2:
                            seg = np.asarray(segment_vertices, dtype=float)
                            line = ax.plot(
                                seg[:, 0],
                                seg[:, 1],
                                color=color,
                                linewidth=linewidths,
                                transform=ccrs.PlateCarree(),
                            )
                            contour_lines.extend(line)
                        segment_vertices = []
                    else:
                        segment_vertices.append(vertex)

                if len(segment_vertices) >= 2:
                    seg = np.asarray(segment_vertices, dtype=float)
                    line = ax.plot(
                        seg[:, 0],
                        seg[:, 1],
                        color=color,
                        linewidth=linewidths,
                        transform=ccrs.PlateCarree(),
                    )
                    contour_lines.extend(line)

            if label_contours:
                finite_vertices = vertices[np.all(np.isfinite(vertices), axis=1)]
                if finite_vertices.size > 0:
                    centroid = np.mean(finite_vertices, axis=0)
                    ax.text(
                        float(centroid[0]),
                        float(centroid[1]),
                        f"{int(level)}",
                        fontsize=8,
                        ha="center",
                        va="center",
                        transform=ccrs.PlateCarree(),
                    )

        contour = contour_lines if contour_lines else None

    return ax, contour


def plot_region_code_contours_on_geomap(
    ax: Any | None = None,
    *,
    draw_coastlines: bool = False,
    draw_gridlines: bool = False,
    contour_levels: Sequence[float] | None = None,
    contour_colors: Sequence[str] | None = None,
    linewidths: float = 1.2,
    label_contours: bool = False,
):
    """Backward-compatible wrapper for :func:`plot_geomap`."""
    return plot_geomap(
        ax=ax,
        draw_coastlines=draw_coastlines,
        draw_gridlines=draw_gridlines,
        draw_contours=True,
        contour_levels=contour_levels,
        contour_colors=contour_colors,
        linewidths=linewidths,
        label_contours=label_contours,
    )


def plot_mapdata(
    newv: SWXData, fileout: str, flav: str, show: bool = False
) -> Path | None:
    """Given gridded data in SWXData format, make the plot and save to fileout.

    Parameters
    ----------
    newv : SWXData
        Gridded data to plot.
    fileout : str
        Output image path.
    flav : str
        REACH sensor flavor label used in the plot title.
    show : bool, optional
        If ``True``, display the plot interactively with ``plt.show()`` after
        saving it.
    """

    colorbarmax = -2
    colorbarmin = -7

    # Make the colorblind friendly colormaps
    # These colors work well for all be true black white colorblind
    cdi = "#093145"  # noqa: F841
    cli = "#3c6478"  # noqa: F841
    cda = "#107896"  # noqa: F841
    cla = "#43abc9"  # noqa: F841
    cdk = "#829356"  # noqa: F841
    clk = "#b5c689"  # noqa: F841
    cdd = "#bca136"  # noqa: F841
    cld = "#efd469"  # noqa: F841
    cdc = "#c2571a"  # noqa: F841
    clc = "#f58b4c"  # noqa: F841
    cdr = "#9a2617"  # noqa: F841
    clr = "#cd594a"  # noqa: F841
    clg = "#F3F4F6"  # noqa: F841
    cdg = "#8B8E95"  # noqa: F841

    greycolors = [clg, cdg]  # noqa: F841
    greencolors = [clg, clk, cdk]  # noqa: F841
    yellowcolors = [clg, cld, cdd]  # noqa: F841
    redcolors = [clg, clr, cdr]  # noqa: F841
    hotcolors = [cld, cdd, cdc, cdr]  # noqa: F841
    colors = [cdi, cdk, cld, cdc, cdr]  # noqa: F841
    bluecolors = [clg, cla, cda, cdi]  # noqa: F841

    bluemap = mpl.colors.LinearSegmentedColormap.from_list("", bluecolors)  # noqa: F841
    pltmap = mpl.colors.LinearSegmentedColormap.from_list("", hotcolors)  # noqa: F841
    greenmap = mpl.colors.LinearSegmentedColormap.from_list("", greencolors)  # noqa: F841
    yellowmap = mpl.colors.LinearSegmentedColormap.from_list("", yellowcolors)  # noqa: F841
    redmap = mpl.colors.LinearSegmentedColormap.from_list("", redcolors)  # noqa: F841

    xylon = newv["xylon"]
    xylat = newv["xylat"]
    region_data_by_enum = {
        Region.SAA: newv["SAA"],
        Region.POLAR_CAP: newv["PC"],
        Region.OUTER_ZONE: newv["outrad"],
        Region.SLOT: newv["slot"],
    }
    # Epoch = newv['Epoch']

    # *****
    pltdos = newv["pltdos"]  #'dA'
    # *****

    # Here we are checking if there is enough data to really make any one of these plots.
    if newv["dataToPlot"] == 0:
        log.info("no data to plot for flavor " + flav + " " + pltdos)
        return None

    if newv["dataToPlot"] == 1:
        # Here we start defining the map we'll be plotting to.

        fig = plt.figure(figsize=(11.69, 8.27))
        ax = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree(central_longitude=0))

        ax.coastlines()

        # and make the grid.
        ax.gridlines(
            draw_labels=True,
            xlocs=np.arange(-180, 180, 30),
            ylocs=np.arange(-90, 90, 10),
            color="gray",
            linestyle="--",
        )

        # Here we will be plotting all the different regions.
        print("making the plot flavor " + flav + " dose " + pltdos)
        cmap_by_region = {
            Region.SAA: redmap,
            Region.POLAR_CAP: yellowmap,
            Region.OUTER_ZONE: bluemap,
            Region.SLOT: greenmap,
        }
        region_meshes: dict[Region, Any] = {}
        for region in Region.ordered():
            log_data = np.where(
                region_data_by_enum[region] > 0,
                np.log10(region_data_by_enum[region]),
                np.nan,
            )
            region_meshes[region] = ax.pcolormesh(
                xylon,
                xylat,
                log_data,
                vmin=colorbarmin,
                vmax=colorbarmax,
                cmap=cmap_by_region[region],
            )

        # Here we can make the contour plots, but they are ugly so currently not turned on.
        # fix bad data in contour plot stuff
        # badinf = np.where(np.isinf(lonlatdos))
        # lonlatdos[badinf] = np.nan
        # badinf = np.where(np.isinf(lonlatdos_lin))
        # lonlatdos_lin[badinf] = np.nan

        # levels = np.logspace(10**colorbarmin, 10**colorbarmax)
        # levels = np.linspace(colorbarmin, colorbarmax, 6)
        # cs = map.contour(xylon, xylat, lonlatdos, levels)

        # Now we are defining the plot title according to the flavour.
        if flav.upper() == "Z":
            pltname = " " + flav + r" $\geq$ 50 keV $e^{-}$, $\geq$ 200 keV $p^{+}$"
        elif flav.upper() == "X":
            pltname = " " + flav + r" $\geq$ 360 keV $e^{-}$, $\geq$ 12 MeV $p^{+}$"
        elif flav.upper() == "W":
            pltname = " " + flav + r"$\geq$ 12 MeV $p^{+}$"
        elif flav.upper() == "Y":
            pltname = " " + flav + r"$\geq$ 1.6 MeV $e^{-}$, $\geq$ 31 MeV $p^{+}$"
        elif flav.upper() == "V":
            pltname = " " + flav + r"$\geq$ 3.4 MeV $e^{-}$, $\geq$ 47 MeV $p^{+}$"
        elif flav.upper() == "U":
            pltname = " " + flav + r"$\geq$ 5.0 MeV $e^{-}$, $\geq$ 57 MeV $p^{+}$"
        else:
            pltname = flav + " " + pltdos
        ax.set_title(newv["plotTitlePre"] + pltname, fontdict={"fontsize": 15})

        # Here we are putting together the color bars for each of the regions.
        intticks = int(np.floor(colorbarmax - colorbarmin) + 1)
        tickemptylabels = [" " for i in range(intticks)]

        # Colorbars stacked vertically
        pos = ax.get_position()
        cbar_height = 0.03
        cbar_width = pos.width
        cbar_x = pos.x0
        cbar_y = pos.y0 - 0.08

        for i, region in enumerate(Region.ordered()):
            cax = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
            cbar = fig.colorbar(
                region_meshes[region], cax=cax, orientation="horizontal"
            )
            cbar.ax.tick_params(direction="in")
            cbar.ax.text(
                0.01,
                0.5,
                region.label,
                transform=cbar.ax.transAxes,
                ha="left",
                va="center",
                color="black",
                fontsize=9,
                weight="bold",
            )
            if i < len(Region.ordered()) - 1:
                cbar.ax.set_xticklabels(tickemptylabels)
            else:
                cbar.set_label("log (rads/sec)", fontsize=10, labelpad=5)
                cbar.ax.xaxis.set_label_position("bottom")
            cbar_y -= cbar_height
        fig.savefig(fileout, orientation="landscape")

        if show:
            plt.show()

        plt.close()

        return Path(fileout)

    return None
