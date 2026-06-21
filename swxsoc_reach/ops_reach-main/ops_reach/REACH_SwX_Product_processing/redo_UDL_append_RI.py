#Here we are loading the relevant python libraries.
#The mpl.user('Agg') is used as this is often run
#from a remote host.

import matplotlib as mpl
mpl.use('Agg')    
import gc
import datetime as dt
import UDL_REACH_indices as URI
import numpy as np
import os
home = os.environ['HOME']


"""

****************
Issues: None identified. 
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

#10 days has been picked as a decent time to make sure the more recent files have been included if they are not made right away. 
#If we go down for longer, this will either have to be updated manually, or do a once run to make up the difference. 
#One could also read in the index files before this, find the last day included and use that. Granted if there are holes which are now data for, 
#this suggested fix would not fix that. 
start_time = dt.datetime(2017, 3, 10, 0, 0, 0) #now - dt.timedelta(days = 25) #start_time = dt.datetime(2017, 3, 10, 0, 0, 0) this would go back to the begining of reach
end_time = now #dt.datetime(2019, 1, 25, 0, 0, 0)#now 

#the integration timestep. Currently all indices are using the same step size. one may want to change this. 
BTstep = 24*60.*60. #this is set to make sure it works for all indicies since they need to all be on the same grid for this file. (seconds)

#This is the output file type names
filepat1 = 'reach_'
plottype = '.png'

#We might not want to always look through 5 days, so put that up here to easily access and change
loop_step = 5
loop_days = np.arange(start_time, end_time, dt.timedelta(days = loop_step), dtype = dt.datetime)

#This is to define the type of data that will be added, The current or "now" files are the last 24 hours, 
#the CDF and CSV files are the finalized formats. 
#At some point we may want to use the database and have another function in the load_REACH.py program. 

cdforcsv = 'cdf' #os.environ['filetype']#'cdf' #this can be specified as csv, cdf, or now 

#This is helping to define the directory paths to find the different types of data.                                                                                     
if cdforcsv == 'now':
    datadir = os.environ['REACHPATH'] + '/aerodata/l1b/current/'            #'/tcs/ago/group/ampere2_reach/aerodata/l1b/current/' #for current                          
elif cdforcsv == 'csv':
    datadir = os.environ['REACHPATH'] + '/aerodata/l1b/mageph/'             #'/tcs/ago/group/ampere2_reach/aerodata/l1b/mageph/' #for csv or cdf                        
elif cdforcsv == 'cdf':
    datadir = os.environ['REACHPATH'] + '/rpac-mirror/daily/'

version = 'v1.29' #the version of the data used, currently only needed for the cdf files but may be updated to the others at a later date. 


#These are the other files and directories which will be either read from or written to
cribdir = os.environ['REACHCODE'] +'/'                            #'/tcs/ago/group/ampere2_reach/reachcode/'
region_crib = os.environ['REGIONCODES']                           #'/home/ajh31116/ssdpy/halford/REACH/data/regions.txt'
fileoutdir = os.environ['REACHPATH'] + '/UDL/'       #'/tcs/ago/group/ampere2_reach/UDL/'
textoutdir = os.environ['REACHPATH'] + '/UDL/'       #'/tcs/ago/group/ampere2_reach/UDL/'
regiondir = os.environ['METADATA'] +'/'             #'/tcs/ago/group/ampere2_reach/metadata/'
regionfile = 'alt_800km.csv'

#Here we define the flavor and relevant dose which goes with it. 
flav = np.array(['x','y', 'u','v', 'w', 'z'])
dose = np.array(['dA', 'dA', 'dB', 'dB', 'dB', 'dB' ])

#now we start calling the primary function and looping through the relevant days. 
for d in loop_days:
    days = d
    print(' start day',days)
    for i, j in zip(flav, dose):
        print('making ' + textoutdir + filepat1+i + 'and ' + textoutdir + filepat1+i)
        URI.append_reach_index(startday =  days, endday = days + dt.timedelta(days = loop_step), 
                               txtoutfile = textoutdir + filepat1+i+'_index',cribdir = cribdir, datadir = datadir,
                               region_crib = region_crib, pngfileout = textoutdir + filepat1+i+'_index',
                               flav = i, online = 'no', local = 'yes', BTstep = BTstep, RI_flavor_file = textoutdir + filepat1+i+'_index'+'.csv',
                               csvorcdf = cdforcsv, dos = j, version = version)
        gc.collect() #This should force python to release non-used memory. 
    #This should happen automatically when coming out of a function, but it doesn't seem to be doing that properly 
