#/bin/bash -l

export PATH="/sbin:/bin:/usr/sbin:/usr/bin:$PATH"

#create the seaes ama                                                                                                                                                                 
source /usr/tcs/anaconda2/bin/activate seaes-ama
#there were issues with the environment variables so I'm sourcing the REACH bash environments here. 
#REACH -specific environment variables.                                                                                                                                                                      
export REACHPATH="/tcs/ago/group/ampere2_reach"
export AERODATA="$REACHPATH/aerodata"
export RPACMIRROR="$REACHPATH/rpac-mirror"
export REACHCODE="$REACHPATH/reachcode"
export METADATA="$REACHPATH/metadata"
export PODSERIALNUMBERS="$REACHCODE/pod_serial_numbers.csv"
export REGIONCODES="$METADATA/alt_800km.csv"


export filetype="now"



#now we just want to say that we're working
#echo "updating the reach L plots"
date

##now we'll make the updated Dos vs L  
echo "updating REACH indicies... need to update code eventually, this is just for testing. "
#
#python /home/ajh31116/ssdpy/halford/REACH/REACH_AJH_web/cron_UDL_append_RI.py
#python /tcs/ago/group/ampere2_reach/UDL/programs/cron_UDL_append_RI.py

python /tcs/ago/group/ampere2_reach/reachcode/python/REACH_Plots/cron_UDL_15min_append_RI.py #cron_UDL_append_RI.py

echo "UDL reach indices are updated"
#echo "Dos vs L plots updated"
