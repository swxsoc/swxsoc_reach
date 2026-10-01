
import matplotlib as mpl

mpl.use('Agg')

import datetime as dt
import UDL_REACH_indicies as URI
import numpy as np
import os
home = os.environ['HOME']


"""
****************
Issues: 
****************
 
The top level main program which runs to update the UDL REACH inidcies, 
This program outputs a csv file and a png file of the different indicies
The different data directories, the start and end times, and the integration time step

********************************************

Example to run the code

ln [x]: run cron_UDL_append_RI
********************************************


"""

__version__ = 1.0 
__author__ = 'A.J. Halford'
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

#Here we define the time range that we want to loop through. We often loop through extra days to make sure we're getting the 
#finalized data into the index. 
nowall = dt.datetime.now()

now = dt.datetime(nowall.year, nowall.month, nowall.day, 0, 0, 0)

start_time = dt.datetime(2017, 4, 15, 0, 0, 0)#now - dt.timedelta(days = 100)start_time = dt.datetime(2017, 3, 10, 0, 0, 0)
end_time = now#dt.datetime(2019, 4, 30, 0, 0, 0)#now

#the integration timestep 
BTstep = 24.*60.*60. #this is set to make sure it works for all indicies since they need to all be on the same grid for this file. 


#This is the output file type names
filepat1 = 'reach_'
plottype = '.png'

#We might not want to always look through 15 days, so put that up here to easily access and change
loop_days = np.arange(start_time, end_time, dt.timedelta(days = 5), dtype = dt.datetime)

#This is to define the type of data that will be added, The current or "now" files are the last 24 hours, 
#the CDF and CSV files are the finalized formats. 
cdforcsv = 'cdf' #this can be specified as csv, cdf, or now 

if cdforcsv == 'now':
    datadir = os.environ['REACHPATH'] + '/aerodata/l1b/current/'  #'/tcs/ago/group/ampere2_reach/aerodata/l1b/current/' #for current       
elif cdforcsv == 'csv':
    datadir = os.environ['REACHPATH'] + '/aerodata/l1b/mageph/'   #'/tcs/ago/group/ampere2_reach/aerodata/l1b/mageph/' #for csv or cdf files                         
elif cdforcsv == 'cdf':
    datadir = os.environ['REACHPATH'] + '/rpac-mirror/daily/'

#These are the other files and directories which will be either read from or written to                                                    
cribdir = os.environ['REACHCODE'] +'/'                            #'/tcs/ago/group/ampere2_reach/reachcode/'                               
region_crib = os.environ['REGIONCODES']                      #'/home/ajh31116/ssdpy/halford/REACH/data/regions.txt'                        
fileoutdir = fileoutdir = os.environ['REACHPATH'] + '/UDL/'       #'/tcs/ago/group/ampere2_reach/UDL/'                                     
textoutdir = fileoutdir = os.environ['REACHPATH'] + '/UDL/'       #'/tcs/ago/group/ampere2_reach/UDL/'                                     
regiondir =  regiondir =  os.environ['METADATA'] +'/'             #'/tcs/ago/group/ampere2_reach/metadata/'                                
regionfile = 'alt_800km.csv'


#Here we define the flavor and relevant dose which goes with it. 
flav = np.array(['x','y', 'u','v', 'w', 'z'])
dose = np.array(['dA', 'dA', 'dB', 'dB', 'dB', 'dB' ])

#now we start calling the primary function and looping through the relevant days. 
for d in loop_days:
    days = d
    print(' start day',days)
    for i, j in zip(flav, dose):
        #print('making ' + textoutdir + filepat1+i + 'and ' + textoutdir + filepat1+i)
        URI.append_reach_index(startday =  days, endday = days + dt.timedelta(days = 15), 
                               txtoutfile = textoutdir + filepat1+i+'_index',cribdir = cribdir, datadir = datadir,
                               region_crib = region_crib, pngfileout = textoutdir + filepat1+i+'_index',
                               flav = i, online = 'no', local = 'yes', BTstep = BTstep, RI_flavor_file = textoutdir + filepat1+i+'_index'+'.csv',
                               csvorcdf = cdforcsv, dos = j)
