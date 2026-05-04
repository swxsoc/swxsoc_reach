********
Releases
********

Notable changes to this project will be documented in this file.
The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`__.

Unreleased
==========

Added
-----

- Added canonical region handling via ``Region`` enum and applied it to map
  masking, contour behavior, and plotting flows.
- Added persistent per-region boolean masks to geomap outputs via
  ``REACHTrack.to_geomap()``, stored as a single multidimensional ``mask``
  support variable.
- Added ``GenericGeoMap.sum_per_region()`` to aggregate map values by region
  using precomputed masks.
- Added ``color_by_region`` option to ``GenericGeoMap.plot()`` to switch
  between per-region rendering and single-colormap rendering.
- Added contour NPZ writer utility ``save_path_to_npz()`` to
  ``swxsoc_reach.util.geom`` next to contour loading utilities.
- Added user documentation page for the new map and track data objects:
  ``docs/user-guide/data_objects.rst``.

Changed
-------

- Updated geomap plotting to consume precomputed region masks directly instead
  of recomputing region assignment at plot time.
- Updated tests and contour-loading usage to current APIs without compatibility
  wrappers for removed legacy helpers.
