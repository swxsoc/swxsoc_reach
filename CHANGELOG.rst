*********
CHANGELOG
*********

Notable changes to this project will be documented in this file.
The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`__.

Unreleased
==========

* Added canonical region handling via ``Region`` enum and applied it to map masking, contour behavior, and plotting flows.
* Added persistent per-region boolean masks to geomap outputs via ``REACHTrack.to_geomap()``, stored as a single multidimensional ``mask`` support variable.
* Added ``GenericGeoMap.sum_per_region()`` to aggregate map values by region using precomputed masks.
* Added ``color_by_region`` option to ``GenericGeoMap.plot()`` to switch between per-region rendering and single-colormap rendering.
* Added contour NPZ writer utility ``save_path_to_npz()`` to ``swxsoc_reach.util.geom`` next to contour loading utilities.
* Added user documentation page for the new map and track data objects: ``docs/user-guide/data_objects.rst``.
* Updated geomap plotting to consume precomputed region masks directly instead of recomputing region assignment at plot time.
* Updated tests and contour-loading usage to current APIs without compatibility wrappers for removed legacy helpers.
* Project foundation and scaffolding were established, including the initial repository setup and template alignment.
* Update to support data pipeline, imports JSON files from UDL and outputs to CDF with ISTP-compliant metadata.
* Runtime and reliability improvements included temporary-path handling, logging improvements, and threaded UDL download support.
* Developer experience was improved through dependency updates, NumPy/doctest constraint refinements, formatting/test updates, and devcontainer/workflow maintenance.
* Documentation and release-readiness work expanded substantially, including docstring updates, Read the Docs/DOI integration, and new customization/changelog documentation.
* Updated docs build behavior to run Sphinx via the active Python environment (``python -m sphinx``) to avoid Homebrew executable conflicts.
* Fixed README badge definitions and URLs (GitHub Actions org links and coverage badge reStructuredText syntax).
* Added package version display to the About page using the Sphinx ``|release|`` substitution.
* Improved changelog discoverability from the docs landing page with a direct link.
