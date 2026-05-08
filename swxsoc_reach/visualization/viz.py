"""A module for visualizing REACH data, including plotting functions and utilities."""

from pathlib import Path
from typing import Any, Sequence

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from cartopy import crs as ccrs
from swxsoc.swxdata import SWXData

from swxsoc_reach import log
from swxsoc_reach.util.enums import Region


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
    from swxsoc_reach.util.util import load_regions

    lookuplon, lookuplat, glook = load_regions()

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

    if lookuplon.size == 0:
        return ax, None

    lon_values = np.unique(lookuplon)
    lat_values = np.unique(lookuplat)
    region_grid = np.full((lat_values.size, lon_values.size), np.nan)

    lon_index = {value: index for index, value in enumerate(lon_values)}
    lat_index = {value: index for index, value in enumerate(lat_values)}
    for lon_value, lat_value, region_code in zip(
        lookuplon,
        lookuplat,
        glook,
        strict=False,
    ):
        region_grid[lat_index[lat_value], lon_index[lon_value]] = region_code

    contour = None
    if draw_contours:
        contour = ax.contour(
            lon_values,
            lat_values,
            region_grid,
            levels=contour_levels,
            colors=contour_colors,
            linewidths=linewidths,
            transform=ccrs.PlateCarree(),
        )

        if label_contours:
            ax.clabel(contour, contour.levels, inline=True, fmt="%d", fontsize=8)

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
    cdi = "#093145"
    cli = "#3c6478"
    cda = "#107896"
    cla = "#43abc9"
    cdk = "#829356"
    clk = "#b5c689"
    cdd = "#bca136"
    cld = "#efd469"
    cdc = "#c2571a"
    clc = "#f58b4c"
    cdr = "#9a2617"
    clr = "#cd594a"
    clg = "#F3F4F6"
    cdg = "#8B8E95"

    greycolors = [clg, cdg]
    greencolors = [clg, clk, cdk]
    yellowcolors = [clg, cld, cdd]
    redcolors = [clg, clr, cdr]
    hotcolors = [cld, cdd, cdc, cdr]
    colors = [cdi, cdk, cld, cdc, cdr]
    bluecolors = [clg, cla, cda, cdi]

    bluemap = mpl.colors.LinearSegmentedColormap.from_list("", bluecolors)
    pltmap = mpl.colors.LinearSegmentedColormap.from_list("", hotcolors)
    greenmap = mpl.colors.LinearSegmentedColormap.from_list("", greencolors)
    yellowmap = mpl.colors.LinearSegmentedColormap.from_list("", yellowcolors)
    redmap = mpl.colors.LinearSegmentedColormap.from_list("", redcolors)

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
            with np.errstate(divide="ignore", invalid="ignore"):
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
