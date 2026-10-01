#Here we are loading the relevant python libraries.
#The mpl.user('Agg') is used as this is often run
#from a remote host. 

import matplotlib as mpl
mpl.use('Agg')
import datetime as dt
import binned_region as br
#import binned_Lvalue as bl
import numpy as np
import os
home = os.environ['HOME']


"""
The top level code to make the latest region maps for the UDL distribution. 
This runs every 10 minutes and updates the lat/lon maps, csv files, and soap files.  

****************
Issues: 
****************

Currently this does not run the Lplots. This is because it was deemed that we didn't 
want to do this quite yet, but may want to in the future. 

********************************************

Example to run the code

ln [x]: run cron_UDL_10min_region_Lplots_and_maps
********************************************


"""

__version__ = 1.0 
__author__ = 'A.J. Halford'
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#size of the scatter points if we were to run the L-plots as well. 
#psize = 1

#determining what days to run. This one only uses the current file, so 1 day. 
now = dt.datetime.now() #- dt.timedelta(days = 30)
start_time = now - dt.timedelta(days = 1)
end_time = now

#what type of data to load in. Again because this is the current day, it's 'now'
cdforcsv = 'now'

#defining where all the different data lives, and where to write things out. 
#This is currently using the enviornment variables which are defined in the shell script and 
#currently in my own bash profile (which should be the same as the reach profile). 
datadir = os.environ['REACHPATH'] + '/aerodata/l1b/current/' #'/tcs/ago/group/ampere2_reach/aerodata/l1b/current/' #for current
cribdir = os.environ['REACHCODE'] +'/'                       #'/tcs/ago/group/ampere2_reach/reachcode/'
region_crib = os.environ['REGIONCODES']                      #'/home/ajh31116/ssdpy/halford/REACH/data/regions.txt'
fileoutdir = os.environ['REACHPATH'] + '/UDL/'               #'/tcs/ago/group/ampere2_reach/UDL/'#aerodata/l1b/current/'
textoutdir = os.environ['REACHPATH'] + '/UDL/'               #'/tcs/ago/group/ampere2_reach/UDL/'#aerodata/l1b/current/'
regiondir =  os.environ['METADATA'] +'/'                     #'/tcs/ago/group/ampere2_reach/metadata/'
regionfile = 'alt_800km.csv'


#output file patterns. 
filepat1 = 'reach_'
filepatmap = 'latest_lat_lon'
#filepatL = '_latest_region_L'
plottype = '.png'

#Since we're going to run through all the flavours and their specific dos, we have them all. 
flav = np.array(['x','y', 'u','v', 'w', 'z'])
dose = np.array(['dA', 'dA', 'dB', 'dB', 'dB', 'dB' ])

print('current day plot being made', start_time, end_time)
for i, j in zip(flav, dose):
    #here we are making the latest region maps
    print('Making the current region maps for flavor', i , ' and dose ', j,)
    br.regionplot(fileout = fileoutdir + filepat1 + i +'_'+filepatmap + plottype,
                  startday = start_time, endday = end_time, local = 'yes', csvorcdf = cdforcsv, flav = i, dos = j,
                  datadir = datadir,  cribdir = cribdir, regiondir = regiondir, regionfile = regionfile, 
                  txtout = 'no', txtoutfile = textoutdir + filepat1 + i+ '_'+ filepatmap,soapregion = 'no', soap = 'yes')
    
    #Uncomment below (and importing binned_L, psize and filepatL above) if we decide to make the L-plots as well. 
    ##here we are making the latest L-value plots 
    #print('Making the current Lplots for flavor', i)
    #fileout = fileoutdir + filepat1 +i+filepatL
    #bl.Lplot_region(fileout = fileout, cribdir = cribdir, datadir = datadir, regiondir = regiondir, regionfile = regionfile,
    #                    startday = start_time, endday = end_time, flav = i, online = 'no', Lmin = 1, Lmax = 10, dosmin = 10**(-7),
    #                   dosmax = 10**(-2), cdforcsv = cdforcsv, psize = psize)

