#Here we are loading the relevant python libraries.
#The mpl.user('Agg') is used as this is often run 
#from a remote host. 

import numpy as np
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import datetime as dt
import yesorno as yn
import load_REACH as lr
import csv
import scipy
import csv
import json
import os
home = os.environ['HOME']
from numpy import meshgrid
from mpl_toolkits.basemap import Basemap
#from matplotlib.pyplot import figure, show, rc, grid
from scipy.stats import mode
#from matplotlib.mlab import griddata

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




"""
****************
Issues: 

comments need to be updated and possibly remove old no longer used functions. - The functions not used for the UDL and web cron jobs have been removed
They are still in the binned_region.py program within the ssdpy git repository in case we need them. 

****************


    Function 1 regionplot: 

    def regionplot(fileout = home + '/Desktop/test_grid.png',cribdir = '../data/',
                datadir = home + '/Data/REACH/', textdir = home + '/Desktop/', 
                startday = dt.datetime(2017, 9, 7, 0, 0, 0), endday = dt.datetime(2017, 9, 10, 23, 59, 59),
                model = 400, dos = 'dA', flav = 'a', online = 'no', 
                bluemarble = 'no',numsteplon = 180, numsteplat = 180,
                colorbarmax= -2, colorbarmin = -7 , local = 'yes',
                region_crib = '../data/regions.txt', csvorcdf = 'csv', txtout = 'no', txtoutfile = home + '/Desktop/test_grid'):
    inputs: 
    fileout -> the file name for the plot that will be made. (string)
    cribdir -> Where the directory for the crib lives to determine all the differnet flavors and models. (string)
    datadir -> The directory path where the data is kept (string)
    textdir -> The directory path for where the text files are written (string)
    startday -> start time to be plotted (datetime)
    endday ->  end time to be plotted (datetime)
    model -> model of the payload (int) 400 defaults to all
    dos -> dose to be plotted (string)
    flav -> flavor of payloads to be used (sting) a defaults to all
    online -> update the crib with the version currently online (string)
    makesoapfile -> do you want the soap files to be made for this timeframe? (yes or no) (string)
    bluemarble -> Use the bluemarble photos as background ('yes') or just the outline of the continents ('no') (string)
    numsteplon ->  the number of bins in longitude (int)
    numsteplat -> the number of bins in latitude (int)
    sat -> the satellite numbers which we want to plot (int)
    numsoapsteps -> The number of time steps for the soap file (int) 
    colorbarmax -> the maximum log10(dose) for the color bar (float or int shouldn't matter)
    colorbarmin -> the minimum log10(dose) for the color bar(float or int shouldn't matter)
    local -> use the local files ('yes') or go and download them ('no') (string)
    soapregion -> This is yes if we want the soap region files to be written. (string) 
    soap -> just a single soap file instead or in addition to files for each region (string) 
    regiondir -> where the crib sheet for the regions lives. (string)
    regionfile -> The file name for the crib sheet. (string) 
    csvorcdf -> Which type of file to use 'csv' or 'cdf', the default is csv (string)
    txtout -> print out the text file (string)
    txtoutfile -> if printing out a text file, the file name (string)
    
    
    outputs: 
    figure of the lat lon plot saved to fileout
    Text file of the map if asked for. 
    if requested, the relevent text files (*.dtt) for soap. 

    *********************************
    example :
    ln[]: import binned_region as br
    ln[]: import datetime as dt
    ln[]: start_time =dt.datetime(2017, 10, 5, 0, 0, 0)
    ln[]: end_time = dt.datetime(2017, 10, 9, 23, 59, 59)
    ln[]: br.regionplot(fileout = '../region_plots/' + days.strftime('%Y_%m_%d')+'_regions.jpg',
                        startday = days, endday = days + dt.timedelta(days = 1),local = 'no')
    *********************************

"""

__version__ = 1.0
__author__ = 'A.J. Halford'
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

def regionplot(fileout = home + '/Desktop/test_grid.png',cribdir = '../data/',
                datadir = home + '/Data/REACH/', textdir = home + '/Desktop/', 
                startday = dt.datetime(2017, 9, 7, 0, 0, 0), endday = dt.datetime(2017, 9, 10, 23, 59, 59),
                model = 400, dos = 'dA', flav = 'a', online = 'no', makesoapfile = 'no', version = 'v1.29', 
                bluemarble = 'no',numsteplon = 360, numsteplat = 180,sat = 10000,numsoapsteps = 1,
                colorbarmax= -2, colorbarmin = -7 , local = 'yes', soapregion = 'yes', soap = 'yes',
                regiondir = '/tcs/ago/group/ampere2_reach/metadata/', regionfile = 'alt_800km.csv', csvorcdf = 'csv', txtout = 'no', txtoutfile = home + '/Desktop/test_grid'):

    """
    Function 1 regionplot: 

    def regionplot(fileout = home + '/Desktop/test_grid.png',cribdir = '../data/',
                datadir = home + '/Data/REACH/', textdir = home + '/Desktop/', 
                startday = dt.datetime(2017, 9, 7, 0, 0, 0), endday = dt.datetime(2017, 9, 10, 23, 59, 59),
                model = 400, dos = 'dA', flav = 'a', online = 'no', 
                bluemarble = 'no',numsteplon = 180, numsteplat = 180,
                colorbarmax= -2, colorbarmin = -7 , local = 'yes',
                region_crib = '../data/regions.txt', csvorcdf = 'csv', txtout = 'no', txtoutfile = home + '/Desktop/test_grid'):
    inputs: 
    fileout -> the file name for the plot that will be made. (string)
    cribdir -> Where the directory for the crib lives to determine all the differnet flavors and models. (string)
    datadir -> The directory path where the data is kept (string)
    textdir -> The directory path for where the text files are written (string)
    startday -> start time to be plotted (datetime)
    endday ->  end time to be plotted (datetime)
    model -> model of the payload (int) 400 defaults to all
    dos -> dose to be plotted (string)
    flav -> flavor of payloads to be used (sting) a defaults to all
    online -> update the crib with the version currently online (string)
    makesoapfile -> do you want the soap files to be made for this timeframe? (yes or no) (string)
    verion -> the version of the data used (string) 
    bluemarble -> Use the bluemarble photos as background ('yes') or just the outline of the continents ('no') (string)
    numsteplon ->  the number of bins in longitude (int)
    numsteplat -> the number of bins in latitude (int)
    sat -> the satellite numbers which we want to plot (int)
    numsoapsteps -> The number of time steps for the soap file (int) 
    colorbarmax -> the maximum log10(dose) for the color bar (float or int shouldn't matter)
    colorbarmin -> the minimum log10(dose) for the color bar(float or int shouldn't matter)
    local -> use the local files ('yes') or go and download them ('no') (string)
    soapregion -> This is yes if we want the soap region files to be written. (string) 
    soap -> just a single soap file instead or in addition to files for each region (string) 
    regiondir -> where the crib sheet for the regions lives. (string)
    regionfile -> The file name for the crib sheet. (string) 
    csvorcdf -> Which type of file to use 'csv' or 'cdf', the default is csv (string)
    txtout -> print out the text file (string)
    txtoutfile -> if printing out a text file, the file name (string)
    
    
    outputs: 
    figure of the lat lon plot saved to fileout
    Text file of the map if asked for. 
    if requested, the relevent text files (*.dtt) for soap. 

    *********************************
    example :
    ln[]: import binned_region as br
    ln[]: import datetime as dt
    ln[]: start_time =dt.datetime(2017, 10, 5, 0, 0, 0)
    ln[]: end_time = dt.datetime(2017, 10, 9, 23, 59, 59)
    ln[]: br.regionplot(fileout = '../region_plots/' + days.strftime('%Y_%m_%d')+'_regions.jpg',
                        startday = days, endday = days + dt.timedelta(days = 1),local = 'no')
    *********************************
    """

    #This is moved to another variable because we use dos later... should probably change this keyword. 
    pltdos = dos

    #Here we are getting the data using the load_REACH functions. As new locations/places to get the data are avalible, those functions should be added to 
    #load_REACH and then the option added here. 
    if csvorcdf == 'cdf':
        dosA, dosB, Lm, MLT, Epoch, lat, lon, satID = lr.cdf_reach(startday = startday, endday = endday, model = model,#lr.dosgeo(startday = startday, endday = endday, model = model
                                             dos = 'dAB', flav = flav, upcrib = online, cribdir = cribdir, version = version,
                                                                   datadir = datadir, locdata = local,sat = sat, retsatID = 'yes', DosFlaga = -1, DosFlagb = -1)
    elif csvorcdf == 'csv':
        dosA, dosB,  lat, lon, csvalt, Epoch, emptyfiles, csvsatID = lr.csv_reach(startday = startday, endday = endday,
                                            locdata = local, retsatID = 'yes',model = model, trackempty = 'yes', sat = sat, 
                                             dos = 'dAB', flav = flav, upcrib = online, cribdir = cribdir,datadir = datadir)
        numsat = len(np.unique(csvsatID))
    elif csvorcdf == 'now':
        dosA, dosB, lat, lon, alt, Epoch, satID = lr.now_reach(model = model, dos = 'dAB', flav =flav, upcrib = online, cribdir = cribdir,
                                                        datadir = datadir, locdata = local, sat = sat)        
    else:
        return 'need to specify either csv or cdf or now for the near realtime data'



    #if len(dosA) <60:
    #    return print('not enough data')
    
    print('for flavor ' + flav + ':')
    print('there are ' + str(len(dosA)) + ' data points in Dos A')
    print('there are ' + str(len(dosB)) + ' data points in Dos B')
    if pltdos in yn.dosA():
        dos = dosA
    else:
        dos = dosB

    #Here we are checking if there is enough data to really make any one of these plots. 
    if len(Epoch) < 1:
        print('no data to plot for flavor ' + flav + ' ' + pltdos)
    
    if len(Epoch) >= 1:
        
        #Here we start defining the map we'll be ploting to. 
        #I've heard rumours that basemap is going away in a few years. May want to find another package to use. 
        plt.figure(figsize=(11.69,8.27))
        map = Basemap(projection='cyl')

        #If we want blue marble use that otherwise draw the coastlines
        if bluemarble in yn.yes():
            map.bluemarble()
        else:
            map.drawcoastlines()

        #and make the grid. 
        map.drawmeridians(np.arange(0,360,30), labels = [0,0,0,1])
        map.drawparallels(np.arange(-90,90,10), labels = [1,0,0,0])

        #here we are reading in the region crib file. 
        reader = csv.DictReader(open(regiondir + regionfile))
        crib = {}
        for row in reader:
            for column, value in row.items():
                crib.setdefault(column, []).append(value)

        #Here we're defining the numbers of the different regions. You can see these in figure
        #http://www-ssd-internal.aero.org/reach/metadata/alt_800km_regions.jpg
        rcSAA = ['1']
        rcinrad = ['-1']
        rcPC = ['-4', '4']
        rcoutrad = ['-3', '3' ]
        rcslot = ['-2', '2']
        lookup = np.array(crib[' Region Code'][:])
        lookup = np.array([np.int(lookup[i]) for i in range(len(lookup))])
        lookuplon = crib[' lon deg'][:]
        lookuplon = np.array([np.int(lookuplon[i]) for i in range(len(lookuplon))])
        lookuplat = crib[' lat deg'][:]
        lookuplat = np.array([np.int(lookuplat[i]) for i in range(len(lookuplat))])
        #now we can find where each of these regions are 



        #now we want to grid everything into 1 deg. bins. Need to make this more general
        #with start stop center and step sizes. !
        lonlatdos = np.zeros((numsteplon,numsteplat))
        lonlatdos_lin = np.zeros((numsteplon,numsteplat))
        lonlatregion = np.zeros((numsteplon,numsteplat))
        xylon = np.zeros((numsteplon,numsteplat))
        xylat = np.zeros((numsteplon,numsteplat))
        SAA = np.zeros((numsteplon,numsteplat))*np.nan 
        inrad = np.zeros((numsteplon,numsteplat))*np.nan 
        PC = np.zeros((numsteplon,numsteplat))*np.nan 
        outrad = np.zeros((numsteplon,numsteplat))*np.nan 
        slot = np.zeros((numsteplon,numsteplat))*np.nan 
        

        for i in np.arange(numsteplon):
            #Here we get the lon bin of the data
            templon = np.where((lon >= i*(360./numsteplon) - 180) & (lon < (i + 1)*(360./numsteplon)- 180))
            glat = lat[templon]
            gdos = dos[templon]

            #here we are getting the lon bin of the regions.
            templooklon = np.where((lookuplon >= i*(360./numsteplon) - 180) & (lookuplon < (i + 1)*(360./numsteplon)- 180))
            glooklat = lookuplat[templooklon]
            glook = lookup[templooklon]

            for j in np.arange(numsteplat):
                #now we are getting the lat bin of the data
                tempglat = np.where((glat >= (j)*(180./numsteplat) - 90) & (glat < (j+1)*(180./numsteplat)-90))
                bindos = gdos[tempglat]
                lonlatdos_lin[i,j] = np.nanmedian(bindos)
                lonlatdos[i,j] = np.log10(np.nanmedian(bindos))
                xylon[i,j],xylat[i,j] = map(((2*i+1)*(360./numsteplon)- 360.)/2., ((2.*j+1)*(180./numsteplat) - 180)/2.)

                templooklat = np.where((glooklat >= (j)*(180./numsteplat) - 90) & (glooklat < (j+1)*(180./numsteplat)-90))
                binlook = glook[templooklat]
                if len(binlook) > 0:
                    #in here we are defining the mode of the data in a lat lon bin, and the mode for the lat lon data in a specific region. 
                    binmode = mode(binlook)
                    lonlatregion[i,j] = np.int(binmode[0])
                    if np.abs(binmode[0]) == 1:
                        SAA[i, j] = (np.nanmedian(bindos))
                    elif np.abs(binmode[0]) == 4:
                        PC[i, j] = (np.nanmedian(bindos))
                    elif np.abs(binmode[0]) == 3:
                        outrad[i, j] = (np.nanmedian(bindos))
                    elif np.abs(binmode[0]) == 2:
                        slot[i, j] = (np.nanmedian(bindos))

                else:
                    #If there is no data in that lat lon bin, it is defined as a nan. 
                    lonlatregion[i,j] = np.nan

        
        
        #Here we will be ploting all the different regions.
        print('making the plot flavor ' + flav + ' dose ' + pltdos)
        mapSAA = map.pcolormesh(xylon, xylat, np.log10(SAA), vmin = colorbarmin, vmax = colorbarmax, cmap=redmap)#'Reds')
        mapPC = map.pcolormesh(xylon, xylat, np.log10(PC), vmin = colorbarmin, vmax = colorbarmax, cmap=yellowmap)#'Purples')
        mapout = map.pcolormesh(xylon, xylat, np.log10(outrad), vmin = colorbarmin, vmax = colorbarmax, cmap=bluemap)#'Blues')
        mapslot = map.pcolormesh(xylon, xylat, np.log10(slot), vmin = colorbarmin, vmax = colorbarmax, cmap=greenmap)#'Greens')

        
        #Here we can make the contour plots, but they are ugly so currently not turned on. 
        #fix bad data in contour plot stuff
        badinf = np.where(np.isinf(lonlatdos))
        lonlatdos[badinf] = np.nan
        badinf = np.where(np.isinf(lonlatdos_lin))
        lonlatdos_lin[badinf] = np.nan

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
        plt.title(np.min(Epoch).strftime('%d %b %Y %H:%M') + ' - '+ np.max(Epoch).strftime('%d %b %Y %H:%M') + pltname , fontdict = {'fontsize' : 15})


        #Here we are putting together the color bars for each of the regions. 
        intticks = np.int(np.floor(colorbarmax - colorbarmin)+1)
        tickemptylabels = [' ' for i in range(intticks)]
        cbartx = colorbarmin + (colorbarmax - colorbarmin)/50
        cbarty = -6.0

        cbarSAA = map.colorbar(mapSAA,location='bottom',pad = "1%",  shrink=0.5, ticks = np.linspace(colorbarmin, colorbarmax, intticks))
        cbarSAA.ax.set_xticklabels(tickemptylabels)
        cbarSAA.ax.tick_params(direction = 'in')
        cbarSAA.ax.text(cbartx, cbarty, 'SAA and Inner Zone', color = 'k', horizontalalignment ='left', verticalalignment = 'bottom')
        cbarSAA.ax.set_ylabel( ' ')

        cbarout = map.colorbar(mapout,location='bottom', pad = "20%", shrink=0.5, ticks = np.linspace(colorbarmin, colorbarmax, intticks))
        cbarout.ax.set_xticklabels(tickemptylabels)
        cbarout.ax.tick_params(direction = 'in')
        cbarout.ax.text(cbartx, cbarty, 'Outer Zone', color = 'k', horizontalalignment ='left', verticalalignment = 'bottom')
        cbarout.ax.set_ylabel( ' ')

        cbarslot = map.colorbar(mapslot,location='bottom', pad = "10%",shrink=0.5, ticks = np.linspace(colorbarmin, colorbarmax, intticks))
        cbarslot.ax.set_xticklabels(tickemptylabels)
        cbarslot.ax.tick_params(direction = 'in')
        cbarslot.ax.text(cbartx, cbarty, 'Slot', color = 'k', horizontalalignment ='left', verticalalignment = 'bottom')
        cbarslot.ax.set_ylabel( ' ')

        cbarPC = map.colorbar(mapPC,location='bottom', pad = "30%", shrink=0.5, ticks = np.linspace(colorbarmin, colorbarmax, intticks))
        cbarPC.ax.tick_params(direction = 'in')
        cbarPC.ax.text(cbartx, cbarty, 'Polar Cap', color = 'k', horizontalalignment ='left', verticalalignment = 'bottom')
        cbarPC.ax.get_yaxis().set_ticks([])
        cbarPC.set_label('log (rads/sec)')
        plt.savefig(fileout, orientation = 'landscape')
        plt.close()

        #now we are writing out the lat lon files into user readible formats. Not sure if people still want the json files or if csv is sufficient. 
        if txtout in yn.yes():
            write = {}
            write['lat'] = xylat.tolist()
            write['lon'] = xylon.tolist()
            write['SAA'] = SAA.tolist()
            write['slot'] = slot.tolist()
            write['ORB'] = outrad.tolist()
            write['PC'] = PC.tolist()
            write['dos'] = lonlatdos_lin.tolist()
            
            with open(txtoutfile+'.json', 'w') as outfile:
                json.dump(write, outfile, default = str, indent = 4, sort_keys = True)
        
        
        with open (txtoutfile+'.csv', 'w') as fh:
            writer = csv.writer(fh, delimiter = ',')
            lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
            lathead = np.append(['lon/lat'], lathead)
            writer.writerow(np.array(lathead))
            for i in range(len(xylon[:,0])):
                templon = np.str(xylon[i,0])
                tempdatarow = [np.str(lonlatdos_lin[i,j]) for j in range(len(xylon[0,:]))]
                temp = np.array(np.append([templon], [tempdatarow]))
                writer.writerow(temp)

        #Now we are writing out the soap files, first the soap file for all lat lons if selected 
        #then the soap files for each of the regions if that one is requested. 

        #because the soap stuff can't have nans's we need to make the bad data/empty grid points points negative negative 
        missingdata = np.where(np.isnan(lonlatdos_lin))
        soapdos = lonlatdos_lin[:]
        soapdos[missingdata] = -99999
        if soap in yn.yes():
            print('making soap file')
            with open (txtoutfile+'_soap.dtt', 'w') as fsoap:
                writer = csv.writer(fsoap)
                writer.writerow(['TABLE_NAME grid 0001'])
                writer.writerow(['Epoch ' + Epoch[0].strftime('%Y %m %d %H %M %S')])
                writer.writerow(['Comment '])
                writer.writerow(['DIM 3'])
                writer.writerow(['COLUMN_NAME Latitude'])
                writer.writerow(['DATA_COLUMNS ' + str(numsteplat)])
                writer.writerow(['ANGLE_UNITS DEGREES 1' ])
                writer.writerow(['Layer_Name Time'])
                writer.writerow(['DATA_LAYERS ' + np.str(numsoapsteps +1)])
                writer.writerow(['Time_Units Hours  1'])
                writer.writerow(['DATA_UNITS Dos'])
                writer.writerow(['DATA REGULAR'])
                
                for step in range(numsoapsteps):
                    writer = csv.writer(fsoap, delimiter = '\t')
                    lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                    lathead = np.append([step], lathead)
                    writer.writerow(np.array(lathead))
                    for i in range(len(xylon[:,0])):
                        templon = np.str(xylon[i,0])
                        tempdatarow = [np.str(soapdos[i,j]) for j in range(len(xylon[0,:]))]
                        temp = np.array(np.append([templon], [tempdatarow]))
                        writer.writerow(temp)
                    templon = np.str(xylon[0,0]+360)
                    tempdatarow = [np.str(soapdos[0,j]) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
                print('now going to write the last table')
                with open (txtoutfile+'_soap.dtt', 'a') as fsoap:
                    writer =  csv.writer(fsoap, delimiter = '\t')
                    lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                    lathead = np.append([np.str((Epoch[-1] - Epoch[0]).total_seconds()/(60.*60.))], lathead)
                    writer.writerow(np.array(lathead))
                    for i in range(len(xylon[:,0])):
                        templon = np.str(xylon[i,0])
                        tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                        temp = np.array(np.append([templon], [tempdatarow]))
                        writer.writerow(temp)
                    templon = np.str(xylon[0,0]+360)
                    tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
                    

        if soapregion in yn.yes(): 
            print('making soap region files')
            print('making soap SAA file')
            badinf = np.where(np.isinf(SAA))
            SAA[badinf] = np.nan
            missingdata = np.where(np.isnan(SAA))
            soapdos = SAA[:]
            soapdos[missingdata] = -99999
            with open (txtoutfile+'_soap_SAA.dtt', 'w') as fsoap:
                writer = csv.writer(fsoap)
                writer.writerow(['TABLE_NAME grid SAA'])
                writer.writerow(['Epoch ' + Epoch[0].strftime('%Y %m %d %H %M %S')])
                writer.writerow(['Comment '])
                writer.writerow(['DIM 3'])
                writer.writerow(['COLUMN_NAME Latitude'])
                writer.writerow(['DATA_COLUMNS ' + str(numsteplat)])
                writer.writerow(['ANGLE_UNITS DEGREES 1' ])
                writer.writerow(['ROW_NAME Longitude'])
                writer.writerow(['DATA_ROWS '  + str(numsteplon+1)])
                writer.writerow(['ANGLE_UNITS DEGREES 1'])
                writer.writerow(['Layer_Name Time'])
                writer.writerow(['DATA_LAYERS ' + np.str(numsoapsteps +1)])
                writer.writerow(['Time_Units Hours  1'])
                writer.writerow(['DATA_UNITS Dos'])
                writer.writerow(['DATA REGULAR'])

            for step in range(numsoapsteps):
                with open (txtoutfile+'_soap_SAA.dtt', 'a') as fsoap:
                    writer = csv.writer(fsoap, delimiter = '\t')
                    lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                    lathead = np.append([step], lathead)
                    writer.writerow(np.array(lathead))
                    for i in range(len(xylon[:,0])):
                        templon = np.str(xylon[i,0])
                        tempdatarow = [np.str(soapdos[i,j]) for j in range(len(xylon[0,:]))]
                        temp = np.array(np.append([templon], [tempdatarow]))
                        writer.writerow(temp)
                    templon = np.str(xylon[0,0]+360)
                    tempdatarow = [np.str(soapdos[0,j]) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
            print('now going to write the last table')
            with open (txtoutfile+'_soap_SAA.dtt', 'a') as fsoap:
                writer =  csv.writer(fsoap, delimiter = '\t')
                lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                lathead = np.append([np.str((Epoch[-1] - Epoch[0]).total_seconds()/(60.*60.))], lathead)
                writer.writerow(np.array(lathead))
                for i in range(len(xylon[:,0])):
                    templon = np.str(xylon[i,0])
                    tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
                templon = np.str(xylon[0,0]+360)
                tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                temp = np.array(np.append([templon], [tempdatarow]))
                writer.writerow(temp)


            print('making soap Slot file')
            badinf = np.where(np.isinf(slot))
            slot[badinf] = np.nan
            missingdata = np.where(np.isnan(slot))
            soapdos = slot[:]
            soapdos[missingdata] = -99999
            with open (txtoutfile+'_soap_Slot.dtt', 'w') as fsoap:
                writer = csv.writer(fsoap)
                writer.writerow(['TABLE_NAME grid '])
                writer.writerow(['Epoch ' + Epoch[0].strftime('%Y %m %d %H %M %S')])
                writer.writerow(['Comment '])
                writer.writerow(['DIM 3'])
                writer.writerow(['COLUMN_NAME Latitude'])
                writer.writerow(['DATA_COLUMNS ' + str(numsteplat)])
                writer.writerow(['ANGLE_UNITS DEGREES 1' ])
                writer.writerow(['ROW_NAME Longitude'])
                writer.writerow(['DATA_ROWS '  + str(numsteplon+1)])
                writer.writerow(['ANGLE_UNITS DEGREES 1'])
                writer.writerow(['Layer_Name Time'])
                writer.writerow(['DATA_LAYERS ' + np.str(numsoapsteps +1)])
                writer.writerow(['Time_Units Hours  1'])
                writer.writerow(['DATA_UNITS Dos'])
                writer.writerow(['DATA REGULAR'])

            for step in range(numsoapsteps):
                with open (txtoutfile+'_soap_Slot.dtt', 'a') as fsoap:
                    writer = csv.writer(fsoap, delimiter = '\t')
                    lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                    lathead = np.append([step], lathead)
                    writer.writerow(np.array(lathead))
                    for i in range(len(xylon[:,0])):
                        templon = np.str(xylon[i,0])
                        tempdatarow = [np.str(soapdos[i,j]) for j in range(len(xylon[0,:]))]
                        temp = np.array(np.append([templon], [tempdatarow]))
                        writer.writerow(temp)
                    templon = np.str(xylon[0,0]+360)
                    tempdatarow = [np.str(soapdos[0,j]) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
            print('now going to write the last table')
            with open (txtoutfile+'_soap_Slot.dtt', 'a') as fsoap:
                writer =  csv.writer(fsoap, delimiter = '\t')
                lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                lathead = np.append([np.str((Epoch[-1] - Epoch[0]).total_seconds()/(60.*60.))], lathead)
                writer.writerow(np.array(lathead))
                for i in range(len(xylon[:,0])):
                    templon = np.str(xylon[i,0])
                    tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
                templon = np.str(xylon[0,0]+360)
                tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                temp = np.array(np.append([templon], [tempdatarow]))
                writer.writerow(temp)


            print('making soap outer radiation belt  file')
            badinf = np.where(np.isinf(outrad))
            outrad[badinf] = np.nan
            missingdata = np.where(np.isnan(outrad))
            soapdos = outrad[:]
            soapdos[missingdata] = -99999
            with open (txtoutfile+'_soap_outBelt.dtt', 'w') as fsoap:
                writer = csv.writer(fsoap)
                writer.writerow(['TABLE_NAME grid outer radiation belt'])
                writer.writerow(['Epoch ' + Epoch[0].strftime('%Y %m %d %H %M %S')])
                writer.writerow(['Comment '])
                writer.writerow(['DIM 3'])
                writer.writerow(['COLUMN_NAME Latitude'])
                writer.writerow(['DATA_COLUMNS ' + str(numsteplat)])
                writer.writerow(['ANGLE_UNITS DEGREES 1' ])
                writer.writerow(['ROW_NAME Longitude'])
                writer.writerow(['DATA_ROWS '  + str(numsteplon+1)])
                writer.writerow(['ANGLE_UNITS DEGREES 1'])
                writer.writerow(['Layer_Name Time'])
                writer.writerow(['DATA_LAYERS ' + np.str(numsoapsteps +1)])
                writer.writerow(['Time_Units Hours  1'])
                writer.writerow(['DATA_UNITS Dos'])
                writer.writerow(['DATA REGULAR'])

            for step in range(numsoapsteps):
                with open (txtoutfile+'_soap_outBelt.dtt', 'a') as fsoap:
                    writer = csv.writer(fsoap, delimiter = '\t')
                    lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                    lathead = np.append([step], lathead)
                    writer.writerow(np.array(lathead))
                    for i in range(len(xylon[:,0])):
                        templon = np.str(xylon[i,0])
                        tempdatarow = [np.str(soapdos[i,j]) for j in range(len(xylon[0,:]))]
                        temp = np.array(np.append([templon], [tempdatarow]))
                        writer.writerow(temp)
                    templon = np.str(xylon[0,0]+360)
                    tempdatarow = [np.str(soapdos[0,j]) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
            print('now going to write the last table')
            with open (txtoutfile+'_soap_outBelt.dtt', 'a') as fsoap:
                writer =  csv.writer(fsoap, delimiter = '\t')
                lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                lathead = np.append([np.str((Epoch[-1] - Epoch[0]).total_seconds()/(60.*60.))], lathead)
                writer.writerow(np.array(lathead))
                for i in range(len(xylon[:,0])):
                    templon = np.str(xylon[i,0])
                    tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
                templon = np.str(xylon[0,0]+360)
                tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                temp = np.array(np.append([templon], [tempdatarow]))
                writer.writerow(temp)


            print('making soap PC file')
            badinf = np.where(np.isinf(PC))
            PC[badinf] = np.nan
            missingdata = np.where(np.isnan(PC))
            soapdos = PC[:]
            soapdos[missingdata] = -99999
            with open (txtoutfile+'_soap_PC.dtt', 'w') as fsoap:
                writer = csv.writer(fsoap)
                writer.writerow(['TABLE_NAME grid PC'])
                writer.writerow(['Epoch ' + Epoch[0].strftime('%Y %m %d %H %M %S')])
                writer.writerow(['Comment '])
                writer.writerow(['DIM 3'])
                writer.writerow(['COLUMN_NAME Latitude'])
                writer.writerow(['DATA_COLUMNS ' + str(numsteplat)])
                writer.writerow(['ANGLE_UNITS DEGREES 1' ])
                writer.writerow(['ROW_NAME Longitude'])
                writer.writerow(['DATA_ROWS '  + str(numsteplon+1)])
                writer.writerow(['ANGLE_UNITS DEGREES 1'])
                writer.writerow(['Layer_Name Time'])
                writer.writerow(['DATA_LAYERS ' + str(numsoapsteps +1)])
                writer.writerow(['Time_Units Hours 1'])
                writer.writerow(['DATA_UNITS Dos'])
                writer.writerow(['DATA REGULAR'])
                
            for step in range(numsoapsteps):
                with open (txtoutfile+'_soap_PC.dtt', 'a') as fsoap:
                    writer = csv.writer(fsoap, delimiter = '\t')
                    lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                    lathead = np.append([step], lathead)
                    writer.writerow(np.array(lathead))
                    for i in range(len(xylon[:,0])):
                        templon = np.str(xylon[i,0])
                        tempdatarow = [np.str(soapdos[i,j]) for j in range(len(xylon[0,:]))]
                        temp = np.array(np.append([templon], [tempdatarow]))
                        writer.writerow(temp)
                    templon = np.str(xylon[0,0]+360)
                    tempdatarow = [np.str(soapdos[0,j]) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
            print('now going to write the last table')            
            with open (txtoutfile+'_soap_PC.dtt', 'a') as fsoap:
                writer = csv.writer(fsoap, delimiter = '\t')
                lathead = [np.str(xylat[0,i]) for i in range(len(xylat[0,:]))]
                lathead = np.append([np.str((Epoch[-1] - Epoch[0]).total_seconds()/(60.*60.))], lathead)
                writer.writerow(np.array(lathead))
                for i in range(len(xylon[:,0])):
                    templon = np.str(xylon[i,0])
                    tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                    temp = np.array(np.append([templon], [tempdatarow]))
                    writer.writerow(temp)
                templon = np.str(xylon[0,0]+360)
                tempdatarow = [np.str(-99999) for j in range(len(xylon[0,:]))]
                temp = np.array(np.append([templon], [tempdatarow]))
                writer.writerow(temp)

