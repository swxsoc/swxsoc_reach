"""
Pipeline entry point for processing REACH UDL files into CDF.
"""

import os
from pathlib import Path
import tempfile

from swxsoc.util.validation import validate

from swxsoc_reach import log
from swxsoc_reach.calibration.transform import build_swxdata
from swxsoc_reach.io.file_tools import read_file
from swxsoc_reach.util.schema import REACHDataSchema

#**********
#NOTE: Aaron changed this call. Not sure if I should have
from swxsoc.swxdata import SWXData
#from swxsoc_reach.swxdata import SWXData
#**********


__all__ = [
    "process_file",
]


def raw_to_mapdata(v: SWXData)-> SWXData:
#def raw_to_mapdata(v):
    # take in raw data in SWXData format and transforms it to gridded data for plotting

    import numpy as np
    import matplotlib as mpl
    mpl.use('TkAgg')
    #import matplotlib.pyplot as plt
    #import datetime as dt
    import csv
    #import scipy
    import csv
    #import json
    #import os
    from numpy import meshgrid
    from scipy.stats import mode
    #from pathlib import Path

    #import warnings
    #from cartopy import crs as ccrs, feature as cfeature
    ##  Suppress warnings issued by Cartopy when downloading data files
    #warnings.filterwarnings('ignore')


    lat = v['lat'].data
    lon = v['lon'].data
    Epoch = v['time']
    tst = v['observations'].data #[ntimes, nsats, ndos]
    dosA = tst[:, :, 0]
    dosB = tst[:, :, 1]
    #dosC = tst[:, :, 2] if tst.shape[2] > 2 else None


    pltdos = 'dA'
    if pltdos == 'dA':
        dos = dosA
    else:
        dos = dosB

    n_times, n_sats = dos.shape

    # Load region lookup
    regionfile_path = '/Users/abrenema/Desktop/code/Aaron/github/swxsoc_reach/swxsoc_reach/data/test/alt_800km - alt_800km.csv'
    lookuplon, lookuplat, glook = [], [], []
    with open(regionfile_path, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            lookuplon.append(float(row[2]))  # lon deg
            lookuplat.append(float(row[1]))  # lat deg
            glook.append(int(row[10]))  # Region Code

    lookuplon = np.array(lookuplon)
    lookuplat = np.array(lookuplat)
    glook = np.array(glook)

    # Create 2D region grid
    region_grid = np.zeros((360, 180), dtype=int)
    lon_indices = ((lookuplon + 180) % 360).astype(int)
    lat_indices = (lookuplat + 90).astype(int)
    region_grid[lon_indices, lat_indices] = glook

    # Grid the data using vectorized operations
    # Initialize as lists to collect all values per bin
    dos_bins = [[[] for _ in range(180)] for _ in range(360)]
    
    for t in range(n_times):
        for s in range(n_sats):
            dos_val = dos[t, s]
            lat_val = lat[t, s]
            lon_val = lon[t, s]
            if not np.isnan(lat_val) and not np.isnan(lon_val):  # Allow nans in dos
                # Convert to grid indices
                lon_idx = int((lon_val + 180) % 360)
                lat_idx = int(lat_val + 90)

                # Ensure indices are within bounds
                if 0 <= lon_idx < 360 and 0 <= lat_idx < 180:
                    dos_bins[lon_idx][lat_idx].append(dos_val)

    # Compute medians
    gridded_dos = np.zeros((360, 180)) * np.nan
    for i in range(360):
        for j in range(180):
            if dos_bins[i][j]:
                gridded_dos[i, j] = np.nanmedian(dos_bins[i][j])

    # Assign to regions using masks
    SAA = np.zeros((360, 180)) * np.nan
    PC = np.zeros((360, 180)) * np.nan
    outrad = np.zeros((360, 180)) * np.nan
    slot = np.zeros((360, 180)) * np.nan

    saa_mask = (region_grid == 1) | (region_grid == -1)
    pc_mask = (region_grid == 2) | (region_grid == -2)
    outrad_mask = (region_grid == 3) | (region_grid == -3)
    slot_mask = (region_grid == 4) | (region_grid == -4)

    SAA[saa_mask] = gridded_dos[saa_mask]
    PC[pc_mask] = gridded_dos[pc_mask]
    outrad[outrad_mask] = gridded_dos[outrad_mask]
    slot[slot_mask] = gridded_dos[slot_mask]

    # Set inf and limiting values to nan
    for arr in [SAA, PC, outrad, slot]:
        badinf = np.where(np.isinf(arr))
        arr[badinf] = np.nan
        # Also set very large values to nan (assuming limiting is >1e30)
        large_vals = np.where(np.abs(arr) > 1e30)
        arr[large_vals] = np.nan

    # Create coordinate grids
    lon_bins = np.arange(-180, 180, 1) + 0.5  # bin centers
    lat_bins = np.arange(-90, 90, 1) + 0.5
    xylon, xylat = np.meshgrid(lon_bins, lat_bins)


    plotTitlePre = str(np.min(Epoch).strftime('%d %b %Y %H:%M') + ' - '+ np.max(Epoch).strftime('%d %b %Y %H:%M'))


    if len(Epoch) < 1:
        dataToPlot = 0
    else:
        dataToPlot = 1




    newv = {'xylon': np.transpose(xylon), 
            'xylat': np.transpose(xylat), 
            'SAA': SAA, 
            'PC': PC, 
            'outrad': outrad, 
            'slot': slot,
            'plotTitlePre': plotTitlePre,
            'dataToPlot': dataToPlot,
            'pltdos': pltdos
            }

    return newv



def plot_mapdata(newv: SWXData, fileout: str, flav: str)-> Path:
    # takes in newv which is the gridded data in SWXData format and makes the plot and saves to fileout.

    import numpy as np
    import matplotlib as mpl
    mpl.use('TkAgg')
    import matplotlib.pyplot as plt
    #import datetime as dt
    #import csv
    #import scipy
    #import csv
    #import json
    #import os
    #home = os.environ['HOME']
    from numpy import meshgrid
    from scipy.stats import mode


    #from swxsoc.swxdata import SWXData
    #from pathlib import Path


    import warnings
    from cartopy import crs as ccrs, feature as cfeature

    #  Suppress warnings issued by Cartopy when downloading data files
    warnings.filterwarnings('ignore')


    colorbarmax= -2
    colorbarmin = -7


    #Make the colorblind friendly colormaps
    #These colors work well for all be true black white colorblind
    cdi = '#093145'
    cli = '#3c6478'
    cda = '#107896'
    cla = '#43abc9'
    cdk = '#829356'
    clk = '#b5c689'
    cdd = '#bca136'
    cld = '#efd469'
    cdc = '#c2571a'
    clc = '#f58b4c'
    cdr = '#9a2617'
    clr = '#cd594a'
    clg = '#F3F4F6'
    cdg = '#8B8E95'  

    greycolors = [clg, cdg]
    greencolors = [clg, clk, cdk]
    yellowcolors = [clg,cld, cdd]
    redcolors = [clg, clr, cdr]
    hotcolors = [cld,cdd,  cdc, cdr]
    colors = [cdi,  cdk, cld,  cdc,  cdr]
    bluecolors = [clg, cla, cda, cdi]

    bluemap = mpl.colors.LinearSegmentedColormap.from_list("", bluecolors)
    pltmap = mpl.colors.LinearSegmentedColormap.from_list("", hotcolors)
    greenmap = mpl.colors.LinearSegmentedColormap.from_list("", greencolors)
    yellowmap = mpl.colors.LinearSegmentedColormap.from_list("", yellowcolors)
    redmap = mpl.colors.LinearSegmentedColormap.from_list("", redcolors)

    xylon = newv['xylon']
    xylat = newv['xylat']
    SAA = newv['SAA']
    PC = newv['PC']
    outrad = newv['outrad']
    slot = newv['slot']
    #Epoch = newv['Epoch']


    #*****
    pltdos = newv['pltdos']  #'dA'
    #*****


    #Here we are checking if there is enough data to really make any one of these plots. 
    if newv['dataToPlot'] == 0:
        print('no data to plot for flavor ' + flav + ' ' + pltdos)

    if newv['dataToPlot'] == 1:
      
        #Here we start defining the map we'll be plotting to. 

        #****
        #NOTE: (Aaron) the CartoPy projection messes up the ability to place the colorbar labels 
        #inside of the colorbar. 
        # See: https://stackoverflow.com/questions/77130818/colorbar-labels-are-not-appearing-when-plotted-in-subplots-as-cartopy-projection     
        #****

        fig = plt.figure(figsize=(11.69,8.27))
        ax = plt.subplot(1, 1, 1, projection=ccrs.PlateCarree(central_longitude=0))

        ax.coastlines()


        #and make the grid. 
        gl = ax.gridlines(draw_labels=True, xlocs=np.arange(-180,180,30), ylocs=np.arange(-90,90,10), color='gray', linestyle='--')



        #Here we will be plotting all the different regions.
        print('making the plot flavor ' + flav + ' dose ' + pltdos)
        mapSAA = ax.pcolormesh(xylon, xylat, np.log10(SAA), vmin = colorbarmin, vmax = colorbarmax, cmap=redmap)#'Reds')
        mapPC = ax.pcolormesh(xylon, xylat, np.log10(PC), vmin = colorbarmin, vmax = colorbarmax, cmap=yellowmap)#'Purples')
        mapout = ax.pcolormesh(xylon, xylat, np.log10(outrad), vmin = colorbarmin, vmax = colorbarmax, cmap=bluemap)#'Blues')
        mapslot = ax.pcolormesh(xylon, xylat, np.log10(slot), vmin = colorbarmin, vmax = colorbarmax, cmap=greenmap)#'Greens')


        
        #Here we can make the contour plots, but they are ugly so currently not turned on. 
        #fix bad data in contour plot stuff
        #badinf = np.where(np.isinf(lonlatdos))
        #lonlatdos[badinf] = np.nan
        #badinf = np.where(np.isinf(lonlatdos_lin))
    # lonlatdos_lin[badinf] = np.nan

        #levels = np.logspace(10**colorbarmin, 10**colorbarmax)
        #levels = np.linspace(colorbarmin, colorbarmax, 6)
        #cs = map.contour(xylon, xylat, lonlatdos, levels)

        #Now we are defining the plot title according to the flavour. 
        if flav.upper() == 'Z':
            pltname = ' ' + flav + r' $\geq$ 50 keV $e^{-}$, $\geq$ 200 keV $p^{+}$'
        elif flav.upper() == 'X':
            pltname = ' ' + flav + r' $\geq$ 360 keV $e^{-}$, $\geq$ 12 MeV $p^{+}$'
        elif flav.upper() == 'W':
            pltname = ' ' + flav + r'$\geq$ 12 MeV $p^{+}$'
        elif flav.upper() == 'Y':
            pltname =' ' +  flav + r'$\geq$ 1.6 MeV $e^{-}$, $\geq$ 31 MeV $p^{+}$'
        elif flav.upper() == 'V':
            pltname =' ' +  flav + r'$\geq$ 3.4 MeV $e^{-}$, $\geq$ 47 MeV $p^{+}$'
        elif flav.upper() == 'U':
            pltname =' ' +  flav + r'$\geq$ 5.0 MeV $e^{-}$, $\geq$ 57 MeV $p^{+}$'
        else:
            pltname = flav + ' ' + pltdos
        #plt.title(np.min(Epoch).strftime('%d %b %Y %H:%M') + ' - '+ np.max(Epoch).strftime('%d %b %Y %H:%M') + pltname , fontdict = {'fontsize' : 15})
        #ax.set_title(np.min(Epoch).strftime('%d %b %Y %H:%M') + ' - '+ np.max(Epoch).strftime('%d %b %Y %H:%M') + pltname , fontdict = {'fontsize' : 15})
        ax.set_title(newv['plotTitlePre'] + pltname , fontdict = {'fontsize' : 15})


        #Here we are putting together the color bars for each of the regions. 
        intticks = int(np.floor(colorbarmax - colorbarmin)+1)
        tickemptylabels = [' ' for i in range(intticks)]




        # Colorbars stacked vertically
        pos = ax.get_position()
        cbar_height = 0.03
        cbar_width = pos.width
        cbar_x = pos.x0
        cbar_y = pos.y0 - 0.08

        # SAA colorbar
        cax_saa = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarSAA = fig.colorbar(mapSAA, cax=cax_saa, orientation='horizontal')
        cbarSAA.ax.set_xticklabels(tickemptylabels)
        cbarSAA.ax.tick_params(direction='in')
        cbarSAA.ax.text(0.05, 0.5, 'SAA and Inner Zone', transform=ax.transAxes, ha='left', va='center', color='black', fontsize=10) #, bbox=dict(boxstyle="round,pad=0.5", facecolor="black", edgecolor="white", alpha=1.0))



        # Outer Zone colorbar
        cbar_y -= cbar_height
        cax_out = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarout = fig.colorbar(mapout, cax=cax_out, orientation='horizontal')
        cbarout.ax.set_xticklabels(tickemptylabels)
        cbarout.ax.tick_params(direction='in')
        cbarout.ax.text(0.05, 0.5, 'Outer Zone', transform=ax.transAxes, ha='left', va='center', color='white', fontsize=10, bbox=dict(boxstyle="round,pad=0.5", facecolor="black", edgecolor="white", alpha=1.0))

        # Slot colorbar
        cbar_y -= cbar_height
        cax_slot = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarslot = fig.colorbar(mapslot, cax=cax_slot, orientation='horizontal')
        cbarslot.ax.set_xticklabels(tickemptylabels)
        cbarslot.ax.tick_params(direction='in')
        cbarslot.ax.text(0.05, 0.5, 'Slot', transform=ax.transAxes, ha='left', va='center', color='white', fontsize=10, bbox=dict(boxstyle="round,pad=0.5", facecolor="black", edgecolor="white", alpha=1.0))

        # Polar Cap colorbar
        cbar_y -= cbar_height
        cax_pc = fig.add_axes([cbar_x, cbar_y, cbar_width, cbar_height])
        cbarPC = fig.colorbar(mapPC, cax=cax_pc, orientation='horizontal')
        cbarPC.ax.tick_params(direction='in')
        cbarPC.ax.text(0.05, 0.5, 'Polar Cap', transform=ax.transAxes, ha='left', va='center', color='white', fontsize=10, bbox=dict(boxstyle="round,pad=0.5", facecolor="black", edgecolor="white", alpha=1.0))
        cbarPC.ax.set_xlabel('log (rads/sec)')
        plt.savefig(fileout, orientation = 'landscape')

        #plt.show()
        plt.close()



def process_file(
    filename: Path,
) -> list[Path]:
    """
    Process a REACH data file from one data level to the next (e.g. UDL file to an ISTP-compliant CDF).

    Reads the file, transforms the data into an
    :class:`~swxsoc.swxdata.SWXData` object, writes a CDF file, and
    runs ISTP validation (logging warnings on any issues without raising).

    Parameters
    ----------
    filename : Path
        Path to the input UDL (JSON or CSV) file.

    Returns
    -------
    list[Path]
        List containing the path to the output CDF file.
    """
    file_path = Path(filename)
    log.info(f"Processing file {file_path}.")

    # Stub Output Files
    output_files = []

    # Read and transform

#*****************************
#CHECK FILE TYPE; IF CDF THEN CREATE MAP CDF. 

    if file_path.suffix.lower() == ".cdf":
        log.info(f"Input file is already a CDF. Creating map CDF.")
        # Create map CDF (stubbed for now)
        v = SWXData(file_path) # read in the CDF file into a SWXData object (stubbed)
        gridded_data = raw_to_mapdata(v)
        gridded_file_path = "gridded_data.cdf"
        gridded_data.save(fileout=gridded_file_path, overwrite=True) # save the gridded data to a new CDF file (stubbed)
        output_files.append(file_path) # add the original CDF to the output files list
        map_cdf_path = plot_mapdata(gridded_data, fileout="map_cdf_output.png")
        output_files.append(map_cdf_path)
        return output_files
    else:
        log.info(f"Input file is not a CDF. Processing as UDL file.")

        data = read_file(file_path)
        reach_data = build_swxdata(data)

        # Check if the LAMBDA_ENVIRONMENT environment variable is set
        lambda_environment = os.getenv("LAMBDA_ENVIRONMENT")
        if lambda_environment:
            output_path = Path(tempfile.gettempdir())
        else:
            output_path = Path.cwd()  # Default to current working directory
        # Write CDF
        cdf_path = reach_data.save(output_path=output_path, overwrite=True)
        log.info(f"Saved CDF to {cdf_path}")
        output_files.append(cdf_path)

        # Validate (warn only, do not raise)
        schema = REACHDataSchema()
        try:
            validation_errors = validate(cdf_path, schema=schema)
            if validation_errors:
                for err in validation_errors:
                    log.warning(f"Validation issue: {err}")
        except Exception as exc:
            log.warning(f"Validation could not complete: {exc}")

        # NOTE: Can add additional processing steps here if needed and return multiple output files as needed.

    return output_files




cdf_test = Path('/Users/abrenema/Desktop/code/Aaron/github/swxsoc_reach/swxsoc_reach/data/test/swxsoc_pipeline_reach_all_l1_prelim_20251201T000000_v1.0.0.cdf')
v = SWXData.load(cdf_test)
newv = raw_to_mapdata(v)

import os
home = os.environ['HOME']
fileout = home + '/Desktop/test_grid.png'

plot_mapdata(newv=newv, fileout=fileout, flav='Z')


print('h')


