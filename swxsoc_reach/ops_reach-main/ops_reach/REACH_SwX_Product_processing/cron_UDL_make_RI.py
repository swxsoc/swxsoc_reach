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
Issues: None identified at this time
****************
 
the top level code to make a reach indice file for the UDL database. 

********************************************

Example to run the code

ln [x]: run cron_UDL_make_RI
********************************************


"""

__version__ = 1.0 
__author__ = 'A.J. Halford'
#~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


#Easiest way to start this is to make a shorter file then appned to it. 
#But if you want to start from the begining of reach, go back to 3/15/2017

nowall = dt.datetime.now()

now = dt.datetime(nowall.year, nowall.month, nowall.day, 0, 0, 0)

start_time = dt.datetime(2019, 3, 20, 0, 0, 0)#now - dt.timedelta(days = 25)
end_time = start_time + dt.timedelta(days = 10)#now - dt.timedelta(days = 10)

#Where do we want to get the data from? Current files (now), csv, or cdf? 
#At somepoint when we start using a database quary instead, that function should be added to load_REACH.py
cdforcsv = 'csv'
#here we find the right data directory to use
if cdforcsv == 'now':
    datadir = os.environ['REACHPATH'] + '/aerodata/l1b/current/' #'/tcs/ago/group/ampere2_reach/aerodata/l1b/current/' #for current  
elif cdforcsv == 'csv': 
    datadir = os.environ['REACHPATH'] + '/aerodata/l1b/mageph/'  #'/tcs/ago/group/ampere2_reach/aerodata/l1b/mageph/' #for csv or cdf files
elif cdforcsv == 'cdf':
    datadir = os.environ['REACHPATH'] + '/rpac-mirror/daily/'


version = 'v1.29' #the version of the data to be used. currently this only is necessary for cdf files but may be updated for other at a later date.  


cribdir = os.environ['REACHCODE'] +'/'                           #'/tcs/ago/group/ampere2_reach/reachcode/'
region_crib = os.environ['REGIONCODES']                          #'/home/ajh31116/ssdpy/halford/REACH/data/regions.txt'
fileoutdir = os.environ['REACHPATH'] + '/UDL/'                   #'/tcs/ago/group/ampere2_reach/UDL/'
textoutdir = os.environ['REACHPATH'] + '/UDL/'                   #'/tcs/ago/group/ampere2_reach/UDL/'
regiondir =  os.environ['METADATA'] +'/'                         #'/tcs/ago/group/ampere2_reach/metadata/'
regionfile = 'alt_800km.csv'

filepat1 = 'reach_'
plottype = '.png'


#This is the full set of REACH flavors and their associated dosimeter. 
flav = np.array(['x','y', 'u','v', 'w', 'z'])
dose = np.array(['dA', 'dA', 'dB', 'dB', 'dB', 'dB' ])

print('current day plot being made', start_time, end_time)
for i, j in zip(flav, dose):
    print('making ' + textoutdir + filepat1+i + 'and ' + textoutdir + filepat1+i)
    URI.make_reach_index(startday =  start_time, endday = end_time, 
                         txtoutfile = textoutdir + filepat1+i+'_index',cribdir = cribdir, datadir = datadir,
                         region_crib = region_crib, pngfileout = textoutdir + filepat1+i+'_index',
                         flav = i, online = 'no', local = 'yes', BTstep = 60.*60*24., 
                         csvorcdf = cdforcsv, dos = j, version = version)
    gc.collect() #This should force python to release non-used memory.
    #This should happen automatically when coming out of a function, but it doesn't seem to be doing that properly 
