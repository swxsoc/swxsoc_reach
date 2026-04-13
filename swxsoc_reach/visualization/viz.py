"""A module for visualizing REACH data, including plotting functions and utilities."""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from cartopy import crs as ccrs
from cartopy import feature as cfeature
from scipy import stats
from swxsoc.swxdata import SWXData

from swxsoc_reach import log


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
    SAA = newv["SAA"]
    PC = newv["PC"]
    outrad = newv["outrad"]
    slot = newv["slot"]
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
        gl = ax.gridlines(
            draw_labels=True,
            xlocs=np.arange(-180, 180, 30),
            ylocs=np.arange(-90, 90, 10),
            color="gray",
            linestyle="--",
        )

        # Here we will be plotting all the different regions.
        print("making the plot flavor " + flav + " dose " + pltdos)
        mapSAA = ax.pcolormesh(
            xylon, xylat, np.log10(SAA), vmin=colorbarmin, vmax=colorbarmax, cmap=redmap
        )  #'Reds')
        mapPC = ax.pcolormesh(
            xylon,
            xylat,
            np.log10(PC),
            vmin=colorbarmin,
            vmax=colorbarmax,
            cmap=yellowmap,
        )  #'Purples')
        mapout = ax.pcolormesh(
            xylon,
            xylat,
            np.log10(outrad),
            vmin=colorbarmin,
            vmax=colorbarmax,
            cmap=bluemap,
        )  #'Blues')
        mapslot = ax.pcolormesh(
            xylon,
            xylat,
            np.log10(slot),
            vmin=colorbarmin,
            vmax=colorbarmax,
            cmap=greenmap,
        )  #'Greens')

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

        # SAA colorbar
        cax_saa = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarSAA = fig.colorbar(mapSAA, cax=cax_saa, orientation="horizontal")
        cbarSAA.ax.set_xticklabels(tickemptylabels)
        cbarSAA.ax.tick_params(direction="in")
        cbarSAA.ax.text(0.01, 0.5, "SAA and Inner Zone", transform=cbarSAA.ax.transAxes, 
                        ha="left", va="center", color="black", fontsize=9, weight="bold")

        # Outer Zone colorbar
        cbar_y -= cbar_height
        cax_out = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarout = fig.colorbar(mapout, cax=cax_out, orientation="horizontal")
        cbarout.ax.set_xticklabels(tickemptylabels)
        cbarout.ax.tick_params(direction="in")
        cbarout.ax.text(0.01, 0.5, "Outer Zone", transform=cbarout.ax.transAxes, 
                       ha="left", va="center", color="black", fontsize=9, weight="bold")

        # Slot colorbar
        cbar_y -= cbar_height
        cax_slot = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarslot = fig.colorbar(mapslot, cax=cax_slot, orientation="horizontal")
        cbarslot.ax.set_xticklabels(tickemptylabels)
        cbarslot.ax.tick_params(direction="in")
        cbarslot.ax.text(0.01, 0.5, "Slot", transform=cbarslot.ax.transAxes, 
                        ha="left", va="center", color="black", fontsize=9, weight="bold")

        # Polar Cap colorbar
        cbar_y -= cbar_height
        cax_pc = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarPC = fig.colorbar(mapPC, cax=cax_pc, orientation="horizontal")
        cbarPC.ax.tick_params(direction="in")
        cbarPC.ax.text(0.01, 0.5, "Polar Cap", transform=cbarPC.ax.transAxes, 
                      ha="left", va="center", color="black", fontsize=9, weight="bold")
        cbarPC.set_label("log (rads/sec)", fontsize=10, labelpad=5)
        cbarPC.ax.xaxis.set_label_position("bottom")
        fig.savefig(fileout, orientation="landscape")

        if show:
            plt.show()

        plt.close()

        return Path(fileout)

    return None
