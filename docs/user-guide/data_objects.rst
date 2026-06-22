.. _data-objects-guide:

*************************
Working with Data Objects
*************************

This page describes the new geospatial data objects produced by
:mod:`swxsoc_reach.track.trackbase` and how to use them in analysis code.

Dosimeter Timeseries Data
==========================

Level 1c files such as `reach_all_l1c_prelim_20260115T000000_v1.0.0.cdf` contain time-series data for all dosimeters and for all satellites for an entire day.
Use :class:`swxsoc_reach.track.trackbase.REACHTrack` to read these files.
This data container provides a number of methods for accessing and manipulating the track data.
The raw data is stored in the ``data`` attribute of the ``REACHTrack`` object, which is a dictionary containing three keys: ``timeseries``, ``support`` and ``spectra``.
Generally, it should not be necessary for users to access the data directly, as the class provides convenient methods for extracting and plotting the data.

For example, use :meth:`REACHTrack.get_track` to extract a time-ordered
:class:`astropy.timeseries.TimeSeries` for a specific satellite.
Each satellite has two dosimeters, so the returned time series contains two dose-rate columns, ``dose0`` and ``dose1``, along with the satellite's geodetic coordinates and a region code.

.. doctest::

   >>> from pathlib import Path
   >>> import swxsoc_reach
   >>> from swxsoc_reach.track.trackbase import REACHTrack
   >>> from swxsoc_reach.util.enums import SensorId
   >>> from swxsoc_reach import _test_file_track

   >>> track = REACHTrack.load(_test_file_track)
   >>> ts = track.get_track(reach_id=SensorId.REACH_101)
   >>> print(ts.colnames)
   ['time', 'dose0', 'dose1', 'longitude', 'latitude', 'altitude', 'region_code']
   >>> len(ts)
   13

To get the flavor for dosimeters for this specific satellite, check the meta data of the track object:

.. doctest::

   >>> ts.meta['flavors']
   [<Flavor.X: 8>, <Flavor.W: 4>]

These are returned as a list of :class:`swxsoc_reach.util.enums.Flavor` objects, which can be used to identify the dosimeter type for each column in the time series.
Refer to :ref:`constellation-guide` for a complete list of all dosimeter flavors and their corresponding sensor IDs.

You can also truncate the track to a specific time range using :meth:`REACHTrack.truncate`, which returns a new ``REACHTrack`` object containing only data within the specified time window.

.. doctest::

   >>> start = track.time[0]  # Start from the first timestamp
   >>> end = track.time[10]  
   >>> truncated = track.truncate(start, end)
   >>> print(f"Original length: {len(track.get_track(SensorId.REACH_101))}")
   Original length: 13
   >>> print(f"Truncated length: {len(truncated.get_track(SensorId.REACH_101))}")
   Truncated length: 11

There are also a couple of built-in plotting methods for quick-look visualization of the track data:

.. doctest::

   >>> track.plot(reach_id=SensorId.REACH_101)  # doctest: +SKIP
     # This will show a multi-panel plot of dose rates and coordinates vs time for the specified satellite.
   >>> track.plotgeo(reach_id=SensorId.REACH_101)  # doctest: +SKIP
     # This will show a global map of the satellite's track colored by dose rate or region code.

GeoMaps
=======

It is frequently useful to visualize the spatial distribution of dose rates across the globe for a given time window.
The :meth:`swxsoc_reach.track.trackbase.REACHTrack.to_geomap` method returns a
:class:`swxsoc_reach.geomap.geomapbase.GenericGeoMap` object.
This object contains gridded spatial data for the entire time window of the track data.
The resolution of the grid can be controlled by the ``lat_bins`` and ``lon_bins`` parameters of the ``to_geomap`` method, which specify the number of latitude and longitude bins to use for the grid.
The :func:`scipy.stats.binned_statistic_2d` function from SciPy is used under the hood to perform the gridding and calculation of statistics.
It calculates every statistic (sum, mean, median, count, min, max, std) for each flavor, so all of these are available as attributes of the returned ``GenericGeoMap`` object.

To create a ``GenericGeoMap`` object, call the ``to_geomap`` method on a ``REACHTrack`` object:

.. doctest::

   >>> geomap = track.to_geomap()

The default gridding uses 180 latitude bins and 360 longitude bins, which corresponds to a 1-degree grid.
You can then access the gridded data for a specific statistic and flavor using the ``map_data`` method:

.. doctest::

   >>> from swxsoc_reach.util.enums import Flavor
   >>> median_map_U = geomap.map_data("median", Flavor.U)
   >>> print(median_map_U.shape)
   (180, 360)

To check how many times each grid cell was sampled, use the ``count_map`` statistic:

.. doctest::

   >>> count_map_U = geomap.map_data("count", Flavor.U)
   >>> print(count_map_U.max())
   4.0

Some flavors are more common than others, so the count map can be used to identify which flavors have sufficient data for analysis.

To generate a coarser map, you can specify the number of latitude and longitude bins when calling ``to_geomap``:

.. doctest::

   >>> import astropy.units as u
   >>> geomap_coarse = track.to_geomap(lat_resolution=10.0*u.deg, lon_resolution=10.0*u.deg)
   >>> median_map_U_coarse = geomap_coarse.map_data("median", Flavor.U)
   >>> print(median_map_U_coarse.shape)
   (18, 36)

Plotting
========

Use :meth:`swxsoc_reach.geomap.geomapbase.GenericGeoMap.plot` to visualize the
map:

.. doctest::

   # Region-aware rendering (default)
   >>> geomap.plot(Flavor.X, statistic='median')  # doctest: +SKIP

   # Overlay contour lines on the plotted data
   >>> geomap.plot(Flavor.X, statistic='count')  # doctest: +SKIP

   # Single-colormap rendering
   >>> geomap.plot(Flavor.X, statistic='median')  # doctest: +SKIP

The ``plot`` method has a number of options for customizing the plot, including the ability to overlay contour lines, change the color scale, and add a colorbar.
Check the docstring of the :meth:`swxsoc_reach.geomap.geomapbase.GenericGeoMap.plot` method for a complete list of options.