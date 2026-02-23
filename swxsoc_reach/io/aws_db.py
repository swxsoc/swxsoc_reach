"""Provides functions to upload data to the time series database for display"""

from astropy.timeseries import TimeSeries
from swxsoc.util.util import record_timeseries


def record_housekeeping(hk_ts: TimeSeries, data_type):
    """Send the housekeeping time series to AWS."""
    my_ts = hk_ts.copy()
    record_timeseries(my_ts, data_type, "reach")
