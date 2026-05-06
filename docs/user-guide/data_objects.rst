.. _data-objects-guide:

************************
Working with Map Objects
************************

This page describes the new geospatial data objects produced by
:mod:`swxsoc_reach.track.trackbase` and how to use them in analysis code.

What ``to_geomap`` returns
==========================

The :meth:`swxsoc_reach.track.trackbase.REACHTrack.to_geomap` method returns a
:class:`swxsoc_reach.geomap.geomapbase.GenericGeoMap` object.

That object stores gridded data in ``support`` variables:

- ``map_data``: 2D dose-rate map with shape ``(nlat, nlon)``.
- ``lon``: 1D longitude bin centers.
- ``lat``: 1D latitude bin centers.
- ``mask``: 3D boolean array with shape ``(nregions, nlat, nlon)``.

The mask axis uses the canonical :class:`swxsoc_reach.util.enums.Region`
ordering:

- axis 0 index 0: SAA and Inner Zone (codes ``+/-1``)
- axis 0 index 1: Polar Cap (codes ``+/-2``)
- axis 0 index 2: Outer Zone (codes ``+/-3``)
- axis 0 index 3: Slot (codes ``+/-4``)

Quick start
===========

.. code-block:: python

   import numpy as np
   from swxsoc_reach.track.trackbase import REACHTrack
   from swxsoc_reach.util.enums import Flavor

   track = REACHTrack.load("path/to/file.cdf")
   geomap = track.to_geomap(flavor=Flavor.ALL)

   print(geomap.map_data.shape)
   print(geomap["mask"].data.shape)

The Trackbase object (REACHTrack)
=================================

The track-level container is
:class:`swxsoc_reach.track.trackbase.REACHTrack`. It represents the original
time-series observations prior to spatial binning.

Use ``REACHTrack`` when you need along-track information (time, sensor, dose,
position). Use ``GenericGeoMap`` when you need gridded lon/lat products and
region-mask workflows.

Typical workflow:

1. Load a track file into ``REACHTrack``.
2. Select a sensor and dosimeter pair with ``get_track`` for a
   :class:`astropy.timeseries.TimeSeries` view.
3. Convert to a gridded map with ``to_geomap`` for region-mask and map-based
   analysis.

.. code-block:: python

   from swxsoc_reach.track.trackbase import REACHTrack
   from swxsoc_reach.util.enums import SensorId, Flavor

   track = REACHTrack.load("path/to/file.cdf")

   # 1D track-style view for one sensor/dosimeter
   ts = track.get_track(reach_id=SensorId.REACH_101, dose_id=0)
   print(ts.colnames)

   # Convert to 2D gridded map object
   geomap = track.to_geomap(flavor=Flavor.ALL)

Key ``REACHTrack`` methods:

- ``get_track(reach_id, dose_id)``: returns a time-ordered
  :class:`astropy.timeseries.TimeSeries` including ``dose``, ``longitude``,
  ``latitude``, ``altitude``, and ``region_code``.
- ``plot(reach_id, dose_id)``: quick-look parameter-vs-time plotting.
- ``plotgeo(color_by="dose" | "region_code")``: global track visualization.
- ``to_geomap(...)``: creates the map object used by the mask-based APIs on
  this page.

Reading region masks
====================

Use the :class:`swxsoc_reach.util.enums.Region` enum to index mask planes
safely instead of hard-coding integers.

.. code-block:: python

   import numpy as np
   from swxsoc_reach.util.enums import Region

   data = geomap.map_data
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

.. code-block:: python

   # Region-aware rendering (default)
   geomap.plot()

   # Single-colormap rendering
   geomap.plot(color_by_region=False)

Per-region totals
=================

Use :meth:`swxsoc_reach.geomap.geomapbase.GenericGeoMap.sum_per_region` for
fast per-region aggregation. This uses the precomputed mask directly.

.. code-block:: python

   region_sums = geomap.sum_per_region()
   # keys: saa, polar_cap, outer_zone, slot
   print(region_sums)

Notes
=====

- Region masks are generated once in ``to_geomap`` and stored in the map object.
- Plotting and per-region sums do not recompute point-in-region geometry.
- Region metadata (labels, keys, code families) comes from
  :class:`swxsoc_reach.util.enums.Region`.
