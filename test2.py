fn = '/Users/abrenema/Desktop/Research/REACH/reach_all_l1c_prelim_20260123T000000_v1.0.0/reach_all_l1c_prelim_20260115T000000_v1.0.0.cdf'


"""
data_objects.rst
"""


#--------------------
    #AARON: BELOW GIVES ISSUE - TO_GEOMAP HAS NO FLAVOR ARGUMENT
from pathlib import Path

import numpy as np

from swxsoc_reach.track.trackbase import REACHTrack
from swxsoc_reach.util.enums import Flavor

track = REACHTrack.load(Path(fn))
geomap = track.to_geomap(flavor=Flavor.ALL)

print(geomap.map_data.shape)
print(geomap["mask"].data.shape)



#--------------------


from astropy.time import Time

from swxsoc_reach.track.trackbase import REACHTrack

track = REACHTrack.load(fn)
    #AARON:OTHER VERSIONS OF LOADING USE PATH(FN) [E.G. track = REACHTrack.load(Path(fn))]


# Extract data for a specific time interval
start = Time("2026-01-15T00:00:00")
end = Time("2026-01-15T01:00:00")
truncated = track.truncate(start, end)
    #AARON: 
    #Exception has occurred: NotImplementedError
    #NDCollection does not support __setitem__. Use NDCollection.update instead
    #  File "/Users/abrenema/Desktop/code/Aaron/github/swxsoc_reach/swxsoc_reach/track/trackbase.py", line 146, in truncate
    #    truncated_data = deepcopy(self)
    #  File "/Users/abrenema/Desktop/code/Aaron/github/swxsoc_reach/test2.py", line 16, in <module>
    #    truncated = track.truncate(start, end)
    #NotImplementedError: NDCollection does not support __setitem__. Use NDCollection.update instead

# Original track is unchanged
print(f"Original length: {len(track.time)}")
print(f"Truncated length: {len(truncated.time)}")


#--------------------

import numpy as np

from swxsoc_reach.util.enums import Region

data = geomap.map_data
mask = geomap["mask"].data

saa_plane = mask[Region.SAA.mask_index]
saa_values = np.where(saa_plane, data, np.nan)
print(np.nansum(saa_values))










