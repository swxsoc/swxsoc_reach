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
   >>> from swxsoc_reach import test_track_file

   >>> track = REACHTrack.load(test_track_file)
   >>> ts = track.get_track(reach_id=SensorId.REACH_101)
   >>> print(ts.colnames)
   ['time', 'dose0', 'dose1', 'longitude', 'latitude', 'altitude', 'region_code']
   >>> len(ts)
   1440

To get the flavor for dosimeters for this specific satellite, check the meta data of the track object:

.. doctest::

   >>> track.meta['flavors']
   [<Flavor.X: 8>, <Flavor.W: 4>]

These are returned as a list of :class:`swxsoc_reach.util.enums.Flavor` objects, which can be used to identify the dosimeter type for each column in the time series.

You can also truncate the track to a specific time range using :meth:`REACHTrack.truncate`, which returns a new ``REACHTrack`` object containing only data within the specified time window.

.. doctest::

   >>> from astropy.time import Time
   >>> start = Time("2025-01-01T00:00:00")
   >>> end = Time("2025-01-01T01:00:00")
   >>> truncated = track.truncate(start, end)
   >>> print(f"Original length: {len(track.get_track(SensorId.REACH_101))}")
   Original length: 1440
   >>> print(f"Truncated length: {len(truncated.get_track(SensorId.REACH_101))}")
   Truncated length: 60

There are also a couple of built-in plotting methods for quick-look visualization of the track data:

.. doctest::

   >>> track.plot(reach_id=SensorId.REACH_101)  # doctest: +SKIP
     # This will show a multi-panel plot of dose rates and coordinates vs time for the specified satellite.
   >>> track.plotgeo(reach_id=SensorId.REACH_101)  # doctest: +SKIP
     # This will show a global map of the satellite's track colored by dose rate or region code.


Key ``REACHTrack`` methods:

- ``get_track(reach_id)``: returns a time-ordered
  :class:`astropy.timeseries.TimeSeries` including ``dose0``, ``dose1``,
  ``longitude``, ``latitude``, ``altitude``, and ``region_code``.
- ``plot(reach_id)``: quick-look parameter-vs-time plotting.
- ``plotgeo(color_by="dose0" | "region_code")``: global track visualization.
- ``truncate(start_time, end_time)``: returns a new ``REACHTrack`` object
  containing only data within the specified time range.
- ``to_geomap(...)``: creates the map object used by the mask-based APIs on
  this page.

Truncating track data by time
=============================

Use :meth:`swxsoc_reach.track.trackbase.REACHTrack.truncate` to extract a
subset of track data within a specified time window. This creates a new
``REACHTrack`` object with all time-indexed data (dose rates, coordinates,
quality flags, and sensor positions) properly sliced.

.. code-block:: python

   from pathlib import Path
   import swxsoc_reach
   from astropy.time import Time
   from swxsoc_reach.track.trackbase import REACHTrack

   sample_cdf = (
       Path(swxsoc_reach.__file__).resolve().parent
       / "data"
       / "test"
       / "reach_all_l1c_prelim_20250904T000000_v1.0.0.cdf"
   )
   track = REACHTrack.load(sample_cdf)

   # Extract data for a specific time interval
   start = Time("2025-01-01T00:00:00")
   end = Time("2025-01-01T01:00:00")
   truncated = track.truncate(start, end)

   # Original track is unchanged
   print(f"Original length: {len(track.time)}")
   print(f"Truncated length: {len(truncated.time)}")



What ``to_geomap`` returns
==========================

The :meth:`swxsoc_reach.track.trackbase.REACHTrack.to_geomap` method returns a
:class:`swxsoc_reach.geomap.geomapbase.GenericGeoMap` object.

The time array is stored in track_data[0].data['timeseries']

- 

That object stores gridded data in ``support`` variables:

- ``median_map``: 3D median dose-rate array with shape
   ``(nflavors, nlat, nlon)``.
- ``mean_map`` / ``count_map`` / ``min_map`` / ``max_map`` / ``std_map``:
   additional per-flavor statistics with the same shape.
- ``lon``: 1D longitude bin centers.
- ``lat``: 1D latitude bin centers.
- ``mask``: 3D boolean array with shape ``(nregions, nlat, nlon)``, where
   ``nregions`` is the number of region families in
   :class:`swxsoc_reach.util.enums.Region` (currently 4).

The mask axis uses the canonical :class:`swxsoc_reach.util.enums.Region`
ordering:

- axis 0 index 0: SAA and Inner Zone (codes ``+/-1``)
- axis 0 index 1: Polar Cap (codes ``+/-2``)
- axis 0 index 2: Outer Zone (codes ``+/-3``)
- axis 0 index 3: Slot (codes ``+/-4``)

Quick start
===========

.. doctest::

   >>> from pathlib import Path
   >>> import swxsoc_reach
   >>> from swxsoc_reach.track.trackbase import REACHTrack

   >>> sample_cdf = (
   ...     Path(swxsoc_reach.__file__).resolve().parent
   ...     / "data"
   ...     / "test"
   ...     / "reach_all_l1c_prelim_20250904T000000_v1.0.0.cdf"
   ... )
   >>> track = REACHTrack.load(sample_cdf)
   >>> geomap = track.to_geomap()

   >>> geomap.median_map.shape
   (6, 180, 360)
   >>> geomap["mask"].data.shape
   (4, 180, 360)

Reading region masks
====================

Use the :class:`swxsoc_reach.util.enums.Region` enum to index mask planes
safely instead of hard-coding integers.

.. code-block:: python

   import numpy as np
   from swxsoc_reach.util.enums import Region

   data = geomap.median_map[0]
   mask = geomap["mask"].data

   saa_plane = mask[Region.SAA.mask_index]
   saa_values = np.where(saa_plane, data, np.nan)
   print(np.nansum(saa_values))

Plotting options
================

Use :meth:`swxsoc_reach.geomap.geomapbase.GenericGeoMap.plot` to visualize the
map:

- ``color_by_region=True`` (default): draws each region with its own colormap.
- ``color_by_region=False``: draws one continuous colormap for full-map context.
- ``draw_contours=True``: overlays contour lines from the plotted data.

.. code-block:: python

   # Region-aware rendering (default)
   geomap.plot()

   # Overlay contour lines on the plotted data
   geomap.plot(draw_contours=True)

   # Single-colormap rendering
   geomap.plot(color_by_region=False)

Map properties
==============

The ``GenericGeoMap`` object provides several useful properties:

- ``median_map``: 3D spatial data array with shape ``(nflavors, nlat, nlon)``.
- ``shape`` or ``dimensions``: Returns ``(nlat, nlon)`` - the spatial dimensions only,
  regardless of whether time-indexed data is present.
- ``extent``: Returns ``(lon_min, lon_max, lat_min, lat_max)`` in degrees.
- ``coordinate_system``: Returns the coordinate system label (typically "geodetic").
- ``flavor``: Returns the data flavor/type associated with the map.

.. code-block:: python

   nlat, nlon = geomap.shape
   print(f"Map dimensions: {nlat} latitude bins x {nlon} longitude bins")
   
   lon_min, lon_max, lat_min, lat_max = geomap.extent
   print(f"Map covers {lat_min} to {lat_max} deg latitude")
