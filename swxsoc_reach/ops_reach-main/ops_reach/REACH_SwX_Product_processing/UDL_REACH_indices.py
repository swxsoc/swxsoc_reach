#Here we are loading the relevant python libraries.
#The mpl.user('Agg') is used as this is often run 
#from a remote host.             

import numpy as np
import datetime as dt
import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import load_REACH as lr
import yesorno as yn
import pandas as pd
import csv
#import json
import os
home = os.environ['HOME']
from dateutil.parser import parse
from scipy.stats import mode


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

greycolors = [clg, cdg]#[clg, clk, cdk]                                                                                \                                  

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

The examples given don't run properly. They need to be made to run off of more generic things...                                                                                                                            
                                                                                                                                               
****************                                                                                                                               
In here are functions that make the REACH indices and then append to those files. 

    Fuction 1:                                                     
    def make_reach_index(startday =  dt.datetime(2017, 2, 9, 0, 0, 0), endday = dt.datetime(2018, 6, 15, 0, 0, 0), txtoutfile = home + '/Desktop/test_grid', 
    cribdir = '../data/', datadir = home + '/Data/REACH/', region_crib = '../data/regions.txt',pngfileout = home + '/Desktop/test_grid',    
    model = 400, flav = 'w', online = 'no', local = 'yes', sat = 1000, BTstep = 24*60*60./5, csvorcdf = 'csv', dos = 'dB', version = 'v1.29'):          

    inputs:                                                                                                                                                                                                              
    startday -> start time to be plotted (datetime)                                   
    endday ->  end time to be plotted (datetime)                        
    txtoutfile -> the file name for the plot that will be made. (string)                            
    cribdir -> Where the directory for the crib lives to determine all the differnet flavors and models. (string)                          
    datadir -> The directory to find the data in. (string)
    region_crib -> where the crib sheet for the regions lives. (string)                                      
    pngoutfile -> The directory path for where the text files are written (string)                                                    
    model -> model of the payload (int) 400 defaults to all                                                                        
    flav -> flavor of payloads to be used (sting) a defaults to all                                                    
    online -> update the crib with the version currently online (string)                                                       
    local -> use the local files ('yes') or go and download them ('no') (string)                                                       
    sat -> the vim of a specific satllite not yet functional. (string) 1000 defaults to all                                                
    BTstep -> the time that you want to average over (float)                                                                                 
    cdforcsv -> use the cdf or csv files (string either 'csv', 'cdf', or 'now')                                                                 
    dos -> dose to be plotted (string)                                                                                                                                                        version -> the version of the data to use (string) 
    
    example :                                                                                                                                                                                                           
    ln[]: import datetime as dt                                                                                                                  
    ln[]: import UDL_REACH_indicies.py as URI                                                                                      
    ln[]: start_time =dt.datetime(2017, 10, 5, 0, 0, 0)                                                                                         
    ln[]: end_time = dt.datetime(2017, 10, 9, 23, 59, 59)                                                                                                                  
    ln[]: URI.make_reach_index(startday = start_time, endday = end_time)                                                                                                                                                                                                                


Function 2: 
def append_reach_index(startday =  dt.datetime(2017, 2, 9, 0, 0, 0), endday = dt.datetime(2018, 6, 15, 0, 0, 0), txtoutfile = home + '/Desktop/test_grid',
                       cribdir = '../data/', datadir = home + '/Data/REACH/', region_crib = '../data/regions.txt',pngfileout = home + '/Desktop/test_grid',
                       model = 400, flav = 'w', online = 'no', local = 'yes', sat = 1000, BTstep = 24*60*60./5, csvorcdf = 'csv', dos = 'dB',
                       RI_flavor_file = '/Desktop/RI_File.csv', version = 'v1.29'):

inputs:                                                                                                                                    
    startday -> start time to be plotted (datetime)                                                                                            
    endday ->  end time to be plotted (datetime)                                                                                               
    txtoutfile -> the file name for the plot that will be made. (string)                                                                          
    cribdir -> Where the directory for the crib lives to determine all the differnet flavors and models. (string)                              
    datadir -> The directory path where the data is kept (string)                                                                              
    region_crib -> where the crib sheet for the regions lives. (string)
    pngoutfile -> The directory path for where the text files are written (string)                                                                
    model -> model of the payload (int) 400 defaults to all                                                                                    
    flav -> flavor of payloads to be used (sting) a defaults to all                                                                            
    online -> update the crib with the version currently online (string)    
    local -> use the local files ('yes') or go and download them ('no') (string)
    sat -> the vim of a specific satllite not yet functional. (string) 1000 defaults to all 
    BTstep -> the time that you want to average over (float)     
    cdforcsv -> use the cdf or csv files (string either 'csv', 'cdf', or 'now')
    dos -> dose to be plotted (string)                                                                                                         
    RI_flavor_file -> the reach index file that will be appended (string)
    version -> the version of the data to use (string) 

 example :                                                                                                                                  
    ln[]: import datetime as dt                                                                                                                
    ln[]: import UDL_REACH_indicies.py as URI
    ln[]: start_time =dt.datetime(2017, 10, 5, 0, 0, 0)                                                                                        
    ln[]: end_time = dt.datetime(2017, 10, 9, 23, 59, 59)               
    ln[]: URI.append_reach_index(startday = start_time, endday = end_time)
"""
__version__ = 1.0
__author__ = 'A.J. Halford'
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~                                                                               


        
def make_reach_index(startday =  dt.datetime(2017, 2, 9, 0, 0, 0), endday = dt.datetime(2018, 6, 15, 0, 0, 0), txtoutfile = home + '/Desktop/test_grid',
                   cribdir = '../data/', datadir = home + '/Data/REACH/', region_crib = '../data/regions.txt',pngfileout = home + '/Desktop/test_grid',
                     model = 400, flav = 'w', online = 'no', local = 'yes', sat = 1000, BTstep = 24*60*60./5, csvorcdf = 'csv', dos = 'dB', version = 'v1.29'):

    """
    Fuction 1:                                                     
    def make_reach_index(startday =  dt.datetime(2017, 2, 9, 0, 0, 0), endday = dt.datetime(2018, 6, 15, 0, 0, 0), txtoutfile = home + '/Desktop/test_grid', 
    cribdir = '../data/', datadir = home + '/Data/REACH/', region_crib = '../data/regions.txt',pngfileout = home + '/Desktop/test_grid',    
    model = 400, flav = 'w', online = 'no', local = 'yes', sat = 1000, BTstep = 24*60*60./5, csvorcdf = 'csv', dos = 'dB'):          

    inputs:                                                                                                                                              
    startday -> start time to be plotted (datetime)                                   
    endday ->  end time to be plotted (datetime)                        
    txtoutfile -> the file name for the plot that will be made. (string)                            
    cribdir -> Where the directory for the crib lives to determine all the differnet flavors and models. (string)                          
    datadir -> The directory to find the data in. (string)
    region_crib -> where the crib sheet for the regions lives. (string)                                      
    pngoutfile -> The directory path for where the text files are written (string)                                                    
    model -> model of the payload (int) 400 defaults to all                                                                        
    flav -> flavor of payloads to be used (sting) a defaults to all                                                    
    online -> update the crib with the version currently online (string)                                                       
    local -> use the local files ('yes') or go and download them ('no') (string)                                                       
    sat -> the vim of a specific satllite not yet functional. (string) 1000 defaults to all                                                
    BTstep -> the time that you want to average over (float)                                                                                 
    cdforcsv -> use the cdf or csv files (string either 'csv', 'cdf', or 'now')   
    dos -> dose to be plotted (string)                                         
    version -> version of the data to use (string) 
    
    example :                                                                                                                                   
    ln[]: import datetime as dt                                                                                                                  
    ln[]: import UDL_REACH_indicies.py as URI                                                                                      
    ln[]: start_time =dt.datetime(2017, 10, 5, 0, 0, 0)                                                                                         
    ln[]: end_time = dt.datetime(2017, 10, 9, 23, 59, 59)                                                                          
    ln[]: URI.make_reach_index(startday = start_time, endday = end_time)                                                    
    """
    
    #because we use dos later... should change this keyword but haven't yet. 
    pltdos = dos
    
    #here we are getting the data. Once we start calling from a database we'll have to update this. 
    #I see this as one additional if statement calling the presumably new load_REACH.py function 
    #We may also want to add the capability of reading in the files Paul makes. Those cdf files have 
    #different variable names so new load_REACH functions will need to be made to read those. 

    #reading in the CDF files coming from APL
    if csvorcdf == 'cdf':
        dosA, dosB, Lm, MLT, Epoch, lat, lon, satID = lr.cdf_reach(startday = startday, endday = endday, model = model, version = version, 
                                                                   dos = 'dAB', flav = flav, upcrib = online, cribdir = cribdir,
                                                                   datadir = datadir, locdata = local,sat = sat, retsatID = 'yes', DosFlaga = -1, DosFlagb = -1)
                               #lr.dosgeo(startday = startday, endday = endday, model = model,
                               #              dos = pltdos, flav = flav, upcrib = online, cribdir = cribdir,
                               #              datadir = datadir, locdata = local,sat = sat)

    #reading in the CSV files Val makes from the XML files I believe. 
    elif csvorcdf == 'csv':
        dosA, dosB,  lat, lon, csvalt, Epoch, emptyfiles, satID = lr.csv_reach(startday = startday, endday = endday,
                                            locdata = local, retsatID = 'yes',model = model, trackempty = 'yes', sat = sat, 
                                             dos = 'dAB', flav = flav, upcrib = online, cribdir = cribdir,datadir = datadir)
        numsat = len(np.unique(satID))

    #reading in the current files Val makes from the 5 minute XML files coming from APL. 
    elif csvorcdf == 'now':
        dosA, dosB, lat, lon, alt, Epoch, satID = lr.now_reach(model = model, dos = 'dAB', flav =flav, upcrib = online, cribdir = cribdir,
                                                        datadir = datadir, locdata = local, sat = sat)
        

    else:
        return 'need to specify either csv or cdf or now for the near realtime data'

    print('got data there is this much', len(Epoch))
    #Here we are checking to make sure thre is some data. 
    if len(Epoch) >= BTstep:
        #now we read in the region crib
        reader = csv.DictReader(open(region_crib), delimiter=',')
        crib = {}
        for row in reader:
            for column, value in row.items():
                crib.setdefault(column, []).append(value)


        #Here we are getting the region codes. There is a space at the begining of the key name. 
        lookup = np.array(crib[' Region Code'][:])
        lookup = np.array([np.int(lookup[i]) for i in range(len(lookup))])
        looklat = np.array(crib[' lat deg'][:])
        looklat = np.array([np.int(looklat[i]) for i in range(len(looklat))])
        looklon = np.array(crib[' lon deg'][:])
        looklon = np.array([np.int(looklon[i]) for i in range(len(looklon))])

        #Val seems to just make all the floats ints and uses that to map to the region code.
        #Here we are going to round first and then make it into an int. Shouldn't make much of a diff
        map2rclat = np.array([int(round(lat[i])) for i in range(len(lat))])
        map2rclon = np.array([int(round(lon[i])) for i in range(len(lon))])

        #find the bad lat and lons and make them nan's
        region = np.zeros(len(dosB))
        for i in range(len(dosB)):
            inreg = np.where((looklat == map2rclat[i]) & (looklon == map2rclon[i]))
            if len(lookup[inreg]) > 0:
                region[i] = lookup[inreg]
            else:
                region[i] = np.nan


        #Here are the region codes for what we are going to make the belt indices
        #For the PC, outrad, and slot, the negatives are in the southern hemisphere
        #There is no distinction between the southern and northern footprints of the
        #inner radiation belt. 
        rcSAA = [1]
        rcIn = [-1]
        rcslot = [-2, 2]
        rcoutrad = [-3, 3 ]
        rcPC = [-4, 4]

        #here we're making our dummy array of the belt index's 
        #numstep = np.int(np.floor((Epoch[-1] - Epoch[0]).total_seconds()/(BTstep)))
        RISAA = [] 
        RIEpoch = []
        #RIIn = []
        RIout = []
        RIslot = []
        RIPC = []
        satnum = []

        #Here we are finding the indices over specific periods.. the steps that we want the belt index to be taken at.  
        for i in np.arange(Epoch[0], Epoch[-1], dt.timedelta(seconds = BTstep), dtype = dt.datetime):
            #Here we are finding the times in the different regions over which we're 
            index = np.where((Epoch >= i) & (Epoch < i+dt.timedelta(seconds = BTstep)))
            binregion = region[index]
            if flav.upper() == 'X':
                binrate = dosA[index]
            elif flav.upper() =='Y':
                binrate = dosA[index]
            else:
                binrate = dosB[index]

            #here we are making the index for the polar cap
            inPC = np.where(np.in1d(binregion, [rcPC]))[0]
            inoutrad = np.where(np.in1d(binregion, [rcoutrad]))[0]
            inslot = np.where(np.in1d(binregion, [rcslot]))[0]
            inIn = np.where(np.in1d(binregion, [rcIn]))[0]
            inSAA = np.where(np.in1d(binregion, [rcSAA]))[0]
            
            satnum = np.append([satnum], [len(np.unique(satID))])
            #Now, if there is data, we find the relevent parameters otherwise we put in nans. 
            if len(binrate[inPC]) > 1:
                RIPC =  np.append(RIPC, [np.nanmedian(binrate[inPC])])
                RIout =  np.append(RIout, [np.nanmedian(binrate[inoutrad])])
                RIslot =  np.append(RIslot, [np.nanmedian(binrate[inslot])])
                #RIIn =  np.append(RIIn, [np.nanmedian(binrate[inIn])])
                RISAA =  np.append(RISAA, [np.nanmedian(binrate[inSAA])])
                
            elif len(binrate[inPC]) <= 1:
                RIPC =  np.append(RIPC, [np.nan])
                #RIIn =  np.append(RIIn, [np.nan])
                RIout =  np.append(RIout, [np.nan])
                RIslot =  np.append(RIslot, [np.nan])
                RISAA =  np.append(RISAA, [np.nan])

            #Here we are making the time array for the indices
            RIEpoch = np.append([RIEpoch], [i+dt.timedelta(seconds = 0.5*BTstep)])

        #Here we write out the reach indices for the given flavour.
        print('making '+ txtoutfile +'.csv' )

        #print('making '+ txtoutfile +'.csv' )
        with open (txtoutfile+'.csv', 'w') as fh:
            writer = csv.writer(fh, delimiter =',')
            writer.writerow([':Data_list: ' + txtoutfile + '.csv'])
            writer.writerow([':Created: ' + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['# '])
            writer.writerow(['# Source: The Aerospace Corporation REACH indices'])
            writer.writerow(['# This file contains the REACH indices for different magnetospheric regions. '])
            if flav.upper() == 'Z':
                writer.writerow(['# This file contains the REACH indices from the model Z dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 0.05 MeV and protons greater than approximately 0.2 MeV'])
                writer.writerow(['# This is a NuDos type dosimiter with no shielding'])
                writer.writerow(['# There are 6 REACH satellites with a model Z dosimeter'])
            if flav.upper() == 'Y':
                writer.writerow(['# This file contains the REACH indices from the model Y dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately1.6 MeV and protons greater than approximately 31 MeV'])
                writer.writerow(['# This is a Std type dosimeter with 24 mils of Mallory shielding which is ~ equivalent to 183 mills of AL'])
                writer.writerow(['# There are 12 REACH satellites with a model Y dosimeter'])
            if flav.upper() == 'X':
                writer.writerow(['# This file contains the REACH indices from the model X dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 0.36 MeV and protons greater than approximately 12 MeV'])
                writer.writerow(['# This is a Std type dosimeter with the ~ equivalent to 32 mills of AL shielding'])
                writer.writerow(['# There are 20 REACH satellites with a model X dosimeter'])
            if flav.upper() == 'W':
                writer.writerow(['# This file contains the REACH indices from the model W dosimeter.'])
                writer.writerow(['# This responds to  protons greater than approximately 12 MeV'])
                writer.writerow(['# This is a HiLET type dosimeter with the ~  equivalent to 32 mills of AL shielding'])
                writer.writerow(['# There are 14 REACH satellites with a model W dosimeter'])
            if flav.upper() == 'V':
                writer.writerow(['# This file contains the REACH indices from the model V dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 3.41 MeV and protons greater than approximately 47 MeV'])
                writer.writerow(['# This is a Std type dosimeter with 56 mils of Mallory shielding which is ~ equivalent to 383 mills of AL'])
                writer.writerow(['# There are 7 REACH satellites with a model V dosimeter'])
            if flav.upper() == 'U':
                writer.writerow(['# This file contains the REACH indices from the model U dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 4.97 MeV and protons greater than approximately 57 MeV'])
                writer.writerow(['# This is a Std type dosimeter with 80 mils of Mallory shielding which is ~ equivalent to 533 mills of AL'])
                writer.writerow(['# There are 5 REACH satellites with a model U dosimeter'])
            writer.writerow(['# format: comma separated values with the following columns'])
            writer.writerow(['# column 01 Year'])
            writer.writerow(['# column 02 month'])
            writer.writerow(['# column 03 day'])
            writer.writerow(['# column 04 Number of satellites which were used to generate the data point labeled as numSat'])
            #writer.writerow(['# column 06 Inner zone index labeled RI_IN'])
            writer.writerow(['# column 05 South Atlantic Anomaly index labeled RI_SAA'])
            writer.writerow(['# column 06 Slot region index labeled RI_Slot'])
            writer.writerow(['# column 07 Outer zone index labeled RI_OZ'])
            writer.writerow(['# column 08 Polar Cap index labeled RI_PC'])

            #header = np.array(['Year','Month', 'Day','MDJ', 'numSat', 'RI_IN', 'RI_SAA', 'RI_Slot', 'RI_OZ', 'RI_PC'])
            header = np.array(['Year','Month', 'Day', 'numSat', 'RI_SAA', 'RI_Slot', 'RI_OZ', 'RI_PC'])
            writer.writerow(np.array(header))
            for i in range(len(RIEpoch)):
                tempdatarow = np.array([RIEpoch[i].strftime('%Y'), RIEpoch[i].strftime('%m'), RIEpoch[i].strftime('%d'), np.str(satnum[i]), np.str(RISAA[i]), np.str(RIslot[i]), np.str(RIout[i]), np.str(RIPC[i])])
                writer.writerow(tempdatarow)
        
        print('making '+ pngfileout +'.png' )
        f, axarr = plt.subplots(1)
        f.tight_layout()
        #we need to remove all zero's if we're plotting on a log scale. 
        finsaa = np.where(RISAA > 0)
        #finin = np.where(RIIn > 0)
        finslot = np.where(RIslot > 0)
        finout = np.where(RIout > 0)
        finPC = np.where(RIPC > 0)
        axarr.semilogy(RIEpoch[finsaa], RISAA[finsaa], label = 'SAA Index')
        #axarr.semilogy(RIEpoch[finin], RIIn[finin], label = 'Inner Zone Index')
        axarr.semilogy(RIEpoch[finslot], RIslot[finslot], label = 'Slot Index')
        axarr.semilogy(RIEpoch[finout], RIout[finout], label = 'Outer Zone Index')
        axarr.semilogy(RIEpoch[finPC], RIPC[finPC], label = 'PC Index')
        axarr.legend(loc = 'upper left')
        axarr.set_ylim(10**(-7), 10**(-3))
        axarr.set_yscale('log', nonposy='clip')
        axarr.set_title('REACH Indices from '+ np.min(RIEpoch[np.where(np.isfinite(RIEpoch))]).strftime("%Y-%m-%d %H:%M:%S") + ' to ' + np.max(RIEpoch[np.where(np.isfinite(RIEpoch))]).strftime("%Y-%m-%d %H:%M:%S"))
        axarr.set_ylabel('Dose rate')
        axarr.grid(True)
        gridlines = axarr.get_xgridlines() + axarr.get_ygridlines()
        for line in gridlines:
            line.set_linestyle('-.')
        plt.savefig(pngfileout + '.png')
        plt.close()


def append_reach_index(startday =  dt.datetime(2017, 2, 9, 0, 0, 0), endday = dt.datetime(2018, 6, 15, 0, 0, 0), txtoutfile = home + '/Desktop/test_grid',
                       cribdir = '../data/', datadir = home + '/Data/REACH/', region_crib = '../data/regions.txt',pngfileout = home + '/Desktop/test_grid',
                       model = 400, flav = 'w', online = 'no', local = 'yes', sat = 1000, BTstep = 24*60*60./5, csvorcdf = 'csv', dos = 'dB',
                       RI_flavor_file = '/Desktop/RI_File.csv', version = 'v1.29'):

    """
    Function 2:                                                                          
    def append_reach_index(startday =  dt.datetime(2017, 2, 9, 0, 0, 0), endday = dt.datetime(2018, 6, 15, 0, 0, 0), txtoutfile = home + '/Desktop/test_grid',      
    cribdir = '../data/', datadir = home + '/Data/REACH/', region_crib = '../data/regions.txt',pngfileout = home + '/Desktop/test_grid',    
    model = 400, flav = 'w', online = 'no', local = 'yes', sat = 1000, BTstep = 24*60*60./5, csvorcdf = 'csv', dos = 'dB',                  
    RI_flavor_file = '/Desktop/RI_File.csv', version = 'v1.29'):  
    
    inputs:                   
    startday -> start time to be plotted (datetime)                                                                                                               
    endday ->  end time to be plotted (datetime)
    txtoutfile -> the file name for the plot that will be made. (string)
    cribdir -> Where the directory for the crib lives to determine all the differnet flavors and models. (string)
    datadir -> The directory path where the data is kept (string)
    region_crib -> where the crib sheet for the regions lives. (string)
    pngoutfile -> The directory path for where the text files are written (string)
    model -> model of the payload (int) 400 defaults to all
    flav -> flavor of payloads to be used (sting) a defaults to all
    online -> update the crib with the version currently online (string)
    local -> use the local files ('yes') or go and download them ('no') (string)
    sat -> the vim of a specific satllite not yet functional. (string) 1000 defaults to all
    BTstep -> the time that you want to average over (float)
    cdforcsv -> use the cdf or csv files (string either 'csv', 'cdf', or 'now')
    dos -> dose to be plotted (string)
    RI_flavor_file -> the reach index file that will be appended (string)
    version -> the version of the data to use (string) 
    
    example :                                                            
    ln[]: import datetime as dt                                          
    ln[]: import UDL_REACH_indicies.py as URI                            
    ln[]: start_time =dt.datetime(2017, 10, 5, 0, 0, 0)  
    ln[]: end_time = dt.datetime(2017, 10, 9, 23, 59, 59)
    ln[]: URI.append_reach_index(startday = start_time, endday = end_time) 
    """
    
    #again as in function 1 should change the key to something different but haven't dont that. 
    pltdos = dos
    
    #Here we request and load the data for the relevant set of satellite(s). Currently one can grab data from the csv, cdf, or current files. 
    #Once we start using the database we should add a function to load_REACH.py and use it here. 
    #Another modification may be to add in an option to use Paul's created cdf's, but they have a different set of key values so will also need their
    #own new function in load_REACH.py

    #Here we read in the cdf files
    
    if csvorcdf == 'cdf':
        dosA, dosB, Lm, MLT, Epoch, lat, lon, satID = lr.cdf_reach(startday = startday, endday = endday, model = model, version = version, 
                                                                   dos = 'dAB', flav = flav, upcrib = online, cribdir = cribdir,
                                                                   datadir = datadir, locdata = local,sat = sat, retsatID = 'yes', DosFlaga = -1, DosFlagb = -1)
    #or the csv files
    elif csvorcdf == 'csv':
        dosA, dosB,  lat, lon, csvalt, Epoch, emptyfiles, satID = lr.csv_reach(startday = startday, endday = endday,
                                            locdata = local, retsatID = 'yes',model = model, trackempty = 'yes', sat = sat,
                                             dos = 'dAB', flav = flav, upcrib = online, cribdir = cribdir,datadir = datadir)
        numsat = len(np.unique(satID))

    #or the current file
    elif csvorcdf == 'now':
        dosA, dosB, lat, lon, alt, Epoch, satID = lr.now_reach(model = model, dos = 'dAB', flav =flav, upcrib = online, cribdir = cribdir,
                                                        datadir = datadir, locdata = local, sat = sat)
        satID = []

    
    else:
        return 'need to specify either csv or cdf or now for the near realtime data'

    print('got data there is this much', len(Epoch))
    #Here we are checking to make sure thre is some data. 
    if len(Epoch) >= BTstep:
        #now we read in the region crib
        reader = csv.DictReader(open(region_crib), delimiter=',')
        crib = {}
        for row in reader:
            for column, value in row.items():
                crib.setdefault(column, []).append(value)


        #Here we are getting the region codes. There is a space at the begining of the key name. 
        lookup = np.array(crib[' Region Code'][:])
        lookup = np.array([np.int(lookup[i]) for i in range(len(lookup))])
        looklat = np.array(crib[' lat deg'][:])
        looklat = np.array([np.int(looklat[i]) for i in range(len(looklat))])
        looklon = np.array(crib[' lon deg'][:])
        looklon = np.array([np.int(looklon[i]) for i in range(len(looklon))])

        #Val seems to just make all the floats ints and uses that to map to the region code.
        #Here we are going to round first and then make it into an int. Shouldn't make much of a diff
        map2rclat = np.array([int(round(lat[i])) for i in range(len(lat))])
        map2rclon = np.array([int(round(lon[i])) for i in range(len(lon))])

        #find the bad lat and lons and make them nan's
        region = np.zeros(len(dosB))
        for i in range(len(dosB)):
            inreg = np.where((looklat == map2rclat[i]) & (looklon == map2rclon[i]))
            if len(lookup[inreg]) > 0:
                region[i] = lookup[inreg]
            else:
                region[i] = np.nan


        #Here are the region codes for what we are going to make the belt indices
        #For the PC, outrad, and slot, the negatives are in the southern hemisphere
        #There is no distinction between the southern and northern footprints of the
        #inner radiation belt. 
        rcSAA = [1]
        rcIn = [-1]
        rcslot = [-2, 2]
        rcoutrad = [-3, 3 ]
        rcPC = [-4, 4]

        #here we're making our dummy array of the belt index's 
        #numstep = np.int(np.floor((Epoch[-1] - Epoch[0]).total_seconds()/(BTstep)))
        RISAA = [] 
        RIEpoch = []
        #RIIn = []
        RIout = []
        RIslot = []
        RIPC = []
        satnum = []

        print('Thre is this much data... in the Epoch', Epoch)
        #print('the first and last epoch are ', Epoch[0], Epoch[-1])
        temp =  np.arange(startday, endday, dt.timedelta(seconds = BTstep), dtype = dt.datetime)
        print('so the range of dates were looking at are ', temp)
        #Here we are finding the indices over specific periods.. the steps that we want the belt index to be taken at.  
        for i in temp:
            #Here we are finding the times in the different regions over which we're 
            #print('looking at time range', i, i+dt.timedelta(seconds = BTstep))
            index = np.where((Epoch >= i) & (Epoch < i+dt.timedelta(seconds = BTstep)))
            binregion = region[index]
            if flav.upper() == 'X':
                binrate = dosA[index]
            elif flav.upper() =='Y':
                binrate = dosA[index]
            else:
                binrate = dosB[index]
            satnum = np.append([satnum],[len(np.unique(satID))])

            #here we are making the index for the polar cap
            inPC = np.where(np.in1d(binregion, [rcPC]))[0]
            inoutrad = np.where(np.in1d(binregion, [rcoutrad]))[0]
            inslot = np.where(np.in1d(binregion, [rcslot]))[0]
            inIn = np.where(np.in1d(binregion, [rcIn]))[0]
            inSAA = np.where(np.in1d(binregion, [rcSAA]))[0]

            #Now, if there is data, we find the relevent parameters otherwise we put in nans. 
            if len(binrate[inPC]) > 1:
                RIPC =  np.append(RIPC, [np.nanmedian(binrate[inPC])])
                RIout =  np.append(RIout, [np.nanmedian(binrate[inoutrad])])
                RIslot =  np.append(RIslot, [np.nanmedian(binrate[inslot])])
                #RIIn =  np.append(RIIn, [np.nanmedian(binrate[inIn])])
                RISAA =  np.append(RISAA, [np.nanmedian(binrate[inSAA])])
                
            elif len(binrate[inPC]) <= 1:
                RIPC =  np.append(RIPC, [np.nan])
                #RIIn =  np.append(RIIn, [np.nan])
                RIout =  np.append(RIout, [np.nan])
                RIslot =  np.append(RIslot, [np.nan])
                RISAA =  np.append(RISAA, [np.nan])

            #Here we are making the time array for the indices
            RIEpoch = np.append([RIEpoch], [i]) #+dt.timedelta(seconds = 0.5*BTstep)])
        
        print('We found data from ', RIEpoch[0], RIEpoch[-1])
        
        #print('length of RIEpoch', len(RIEpoch))
        old_RI_data = pd.read_csv(RI_flavor_file, sep = ',', skiprows = 18)
        old_year = old_RI_data['Year']
        old_month = old_RI_data['Month']
        old_day = old_RI_data['Day']
        old_Epoch = np.array([dt.datetime.strptime(np.str(old_year[i]) + np.str(old_month[i]) + np.str(old_day[i]), '%Y%m%d') for i in range(len(old_year))])
        #old_RIIN = np.array([np.float(old_RI_data['RI_IN'][i]) for i in range(len(old_RI_data['RI_IN']))])
        old_RISAA = np.array([np.float(old_RI_data['RI_SAA'][i]) for i in range(len(old_RI_data['RI_SAA']))])
        old_RISlot = np.array([np.float(old_RI_data['RI_Slot'][i]) for i in range(len(old_RI_data['RI_Slot']))])
        old_RIOZ = np.array([np.float(old_RI_data['RI_OZ'][i]) for i in range(len(old_RI_data['RI_OZ']))])
        old_RIPC = np.array([np.float(old_RI_data['RI_PC'][i]) for i in range(len(old_RI_data['RI_PC']))])
        old_satnum = np.array([np.float(old_RI_data['numSat'][i]) for i in range(len(old_RI_data['numSat']))])
        #This is where we need to put the dummy nan arrays (except for the Epoch, that needs to have the right grid). 
        
        print('length of old file', len(old_Epoch))
        print('length of generated data', len(RIEpoch))

        if len(RIEpoch) == 0: 
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('somthing seems to have gone wrong')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')
            print('')

            
            RIEpoch = np.arange(startday, endday, dt.timedelta(seconds = BTstep), dtype = dt.datetime)
            #RIIn = np.zeros(len(RIEpoch)) * np.nan
            RISAA = np.zeros(len(RIEpoch)) * np.nan
            RIslot = np.zeros(len(RIEpoch)) * np.nan
            RIout = np.zeros(len(RIEpoch)) * np.nan
            RIPC = np.zeros(len(RIEpoch)) * np.nan
        
        print('length of new stuff', len(RIEpoch))

        #Here we're going to find all the pre-append stuff 
        if csvorcdf == 'now':
            nowall = dt.datetime.now()
            minEpoch = dt.datetime(nowall.year, nowall.month, nowall.day, 0,0, 0)
            maxEpoch = minEpoch + dt.timedelta(days =1)
        else:
            minEpoch = temp[0]#np.nanmin(RIEpoch)
            maxEpoch = temp[-1]#np.nanmax(RIEpoch)
        print('the min and max epochs of the new stuff', minEpoch, maxEpoch)
        preRI = np.where(old_Epoch < minEpoch)
        #Here we find all the post - append stuff
        postRI = np.where(old_Epoch > maxEpoch)
        
        #Now we can append it all together...
        if preRI[0].size > 0:
            RIEpoch = np.append([old_Epoch[preRI]],[RIEpoch]) 
            RISAA = np.append([old_RISAA[preRI]], [RISAA]) 
            #RIIn = np.append([old_RIIN[preRI]], [RIIn]) 
            RIslot = np.append([old_RISlot[preRI]], [RIslot]) 
            RIout = np.append([old_RIOZ[preRI]], [RIout]) 
            RIPC = np.append([old_RIPC[preRI]], [RIPC]) 
            satnum = np.append([old_satnum[preRI]], [satnum])
        if postRI[0].size > 0:
            RIEpoch = np.append([RIEpoch], [old_Epoch[postRI]]) 
            RISAA = np.append([RISAA], [old_RISAA[postRI]]) 
            #RIIn = np.append([RIIn], [old_RIIN[postRI]]) 
            RIslot = np.append([RIslot], [old_RISlot[postRI]]) 
            RIout = np.append([RIout], [old_RIOZ[postRI]]) 
            RIPC = np.append([RIPC], [old_RIPC[postRI]]) 
            satnum = np.append([satnum], [old_satnum[postRI]])
        
        print('length of new file', len(RIEpoch))
        
        print('making '+ txtoutfile +'.csv' )
        with open (txtoutfile+'.csv', 'w') as fh:
            writer = csv.writer(fh, delimiter =',')
            writer.writerow([':Data_list: ' + txtoutfile + '.csv'])
            writer.writerow([':Created: ' + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            writer.writerow(['# '])
            writer.writerow(['# Source: The Aerospace Corporation REACH indices'])
            writer.writerow(['# This file contains the REACH indices for different magnetospheric regions. '])
            if flav.upper() == 'Z':
                writer.writerow(['# This file contains the REACH indices from the model Z dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 0.05 MeV and protons greater than approximately 0.2 MeV'])
                writer.writerow(['# This is a NuDos type dosimiter with no shielding'])
                writer.writerow(['# There are 6 REACH satellites with a model Z dosimeter'])
            if flav.upper() == 'Y':
                writer.writerow(['# This file contains the REACH indices from the model Y dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately1.6 MeV and protons greater than approximately 31 MeV'])
                writer.writerow(['# This is a Std type dosimeter with 24 mils of Mallory shielding which is ~ equivalent to 183 mills of AL'])
                writer.writerow(['# There are 12 REACH satellites with a model Y dosimeter'])
            if flav.upper() == 'X':
                writer.writerow(['# This file contains the REACH indices from the model X dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 0.36 MeV and protons greater than approximately 12 MeV'])
                writer.writerow(['# This is a Std type dosimeter with the ~ equivalent to 32 mills of AL shielding'])
                writer.writerow(['# There are 20 REACH satellites with a model X dosimeter'])
            if flav.upper() == 'W':
                writer.writerow(['# This file contains the REACH indices from the model W dosimeter.'])
                writer.writerow(['# This responds to  protons greater than approximately 12 MeV'])
                writer.writerow(['# This is a HiLET type dosimeter with the ~  equivalent to 32 mills of AL shielding'])
                writer.writerow(['# There are 14 REACH satellites with a model W dosimeter'])
            if flav.upper() == 'V':
                writer.writerow(['# This file contains the REACH indices from the model V dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 3.41 MeV and protons greater than approximately 47 MeV'])
                writer.writerow(['# This is a Std type dosimeter with 56 mils of Mallory shielding which is ~ equivalent to 383 mills of AL'])
                writer.writerow(['# There are 7 REACH satellites with a model V dosimeter'])
            if flav.upper() == 'U':
                writer.writerow(['# This file contains the REACH indices from the model U dosimeter.'])
                writer.writerow(['# This responds to electrons greater than approximately 4.97 MeV and protons greater than approximately 57 MeV'])
                writer.writerow(['# This is a Std type dosimeter with 80 mils of Mallory shielding which is ~ equivalent to 533 mills of AL'])
                writer.writerow(['# There are 5 REACH satellites with a model U dosimeter'])
            writer.writerow(['# format: comma separated values with the following columns'])
            writer.writerow(['# column 01 Year'])
            writer.writerow(['# column 02 month'])
            writer.writerow(['# column 03 day'])
            #writer.writerow(['# column 04 Modified Julian Day labeled as MJD from 1950 (CNES JD epoch = 0h Jan 1, 1950)'])
            writer.writerow(['# column 04 Number of satellites which were used to generate the data point labeled as numSat'])
            #writer.writerow(['# column 06 Inner zone index labeled RI_IN'])
            writer.writerow(['# column 05 South Atlantic Anomaly index labeled RI_SAA'])
            writer.writerow(['# column 06 Slot region index labeled RI_Slot'])
            writer.writerow(['# column 07 Outer zone index labeled RI_OZ'])
            writer.writerow(['# column 0 8Polar Cap index labeled RI_PC'])

            #header = np.array(['Year','Month', 'Day','MDJ', 'numSat', 'RI_IN', 'RI_SAA', 'RI_Slot', 'RI_OZ', 'RI_PC'])
            header = np.array(['Year','Month', 'Day', 'numSat', 'RI_SAA', 'RI_Slot', 'RI_OZ', 'RI_PC'])
            writer.writerow(np.array(header))
            for i in range(len(RIEpoch)):
                #tempdatarow = np.array([RIEpoch[i].strftime('%Y'), RIEpoch[i].strftime('%m'), RIEpoch[i].strftime('%d'), np.str(np.nan),np.str(np.nan), np.str(RIIn[i]), np.str(RISAA[i]), np.str(RIslot[i]), np.str(RIout[i]), np.str(RIPC[i])])
                mjd = 33282.0 + np.array( RIEpoch[i].toordinal()-dt.datetime(1950,1,1).toordinal()) +  RIEpoch[i].hour/24.0 +  RIEpoch[i].minute/24.0/60.0 + RIEpoch[i].second/24.0/60.0/60.0
                #tempdatarow = np.array([RIEpoch[i].strftime('%Y'), RIEpoch[i].strftime('%m'), RIEpoch[i].strftime('%d'), np.str(mjd), np.str(satnum[i]), np.str(RISAA[i]), np.str(RIslot[i]), np.str(RIout[i]), np.str(RIPC[i])])
                tempdatarow = np.array([RIEpoch[i].strftime('%Y'), RIEpoch[i].strftime('%m'), RIEpoch[i].strftime('%d'), np.str(satnum[i]), np.str(RISAA[i]), np.str(RIslot[i]), np.str(RIout[i]), np.str(RIPC[i])])
                writer.writerow(tempdatarow)
        
        print('making '+ pngfileout +'.png' )
        print('min and max of indices')
        print('RI_SAA', type(RISAA), (RISAA[0]))
        #print('RI_In', np.nanmin(RIIn), np.nanmax(RIIn))
        print('RI_slot', np.nanmin(RIslot), np.nanmax(RIslot))
        print('RI_out', np.nanmin(RIout), np.nanmax(RIout))
        print('RI_PC', np.nanmin(RIPC), np.nanmax(RIPC))
        
        font = {'family' : 'normal',
                'weight' : 'bold',
                'size'   : 22}
        mpl.rc('font', **font)
        fig, axarr = plt.subplots(nrows=4, ncols=1, figsize = (8*5, 8*4.25))
        #f.tight_layout()
        #we need to remove all zero's if we're plotting on a log scale.                                                                                                    

        axarr[0].semilogy(RIEpoch, RISAA, c = cdr, label = 'SAA Index')
        axarr[0].legend(loc = 'upper left')
        axarr[0].set_ylim(10**(-7), 10**(-3))
        axarr[0].set_ylabel('Dose rate', fontsize=32)
        axarr[0].grid(True)
        gridlines = axarr[0].get_xgridlines() + axarr[0].get_ygridlines()
        for line in gridlines:
            line.set_linestyle('-.')

        
        axarr[1].semilogy(RIEpoch, RIslot, c = cdk,  label = 'Slot Index')
        axarr[1].legend(loc = 'upper left')
        axarr[1].set_ylim(10**(-7), 10**(-3))
        axarr[1].set_ylabel('Dose rate', fontsize=32)
        axarr[1].grid(True)
        gridlines = axarr[1].get_xgridlines() + axarr[1].get_ygridlines()
        for line in gridlines:
            line.set_linestyle('-.')

        axarr[2].semilogy(RIEpoch, RIout, c = cda, label = 'Outer Zone Index')
        axarr[2].legend(loc = 'upper left')
        axarr[2].set_ylim(10**(-7), 10**(-3))
        axarr[2].set_ylabel('Dose rate', fontsize=32)
        axarr[2].grid(True)
        gridlines = axarr[2].get_xgridlines() + axarr[2].get_ygridlines()
        for line in gridlines:
            line.set_linestyle('-.')

        axarr[3].semilogy(RIEpoch, RIPC, c = cdd, label = 'PC Index')
        axarr[3].legend(loc = 'upper left')
        axarr[3].set_ylim(10**(-7), 10**(-3))
        axarr[3].set_ylabel('Dose rate', fontsize=32)
        axarr[3].grid(True)
        gridlines = axarr[3].get_xgridlines() + axarr[3].get_ygridlines()
        for line in gridlines:
            line.set_linestyle('-.')
        axarr[3].set_xlabel('Year Month UT Time', fontsize=32)
        #maxtimeindex = np.where(np.isfinite(RIEpoch))
        #mintimeindex = np.where(np.isfinite(RIEpoch))
        #maxtime = RIEpoch[maxtimeindex]
        #mintime = RIEpoch[mintimeindex]
        #fig.suptitle(flav.upper() + ' REACH Indices from '+ maxtime[0].strftime("%Y-%m-%d %H:%M:%S") + ' to ' + mintime[0].strftime("%Y-%m-%d %H:%M:%S"), fontsize = 'xx-large')
        fig.suptitle(flav.upper() + ' REACH Indices from '+ RIEpoch[0].strftime("%Y-%m-%d %H:%M:%S") + ' to ' + RIEpoch[-1].strftime("%Y-%m-%d %H:%M:%S"), fontsize = 'xx-large')
        plt.savefig(txtoutfile + '.png')
        plt.close()
