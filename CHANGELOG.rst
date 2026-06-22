=========
CHANGELOG
=========

Notable changes to this project will be documented in this file.
The format is based on `Keep a Changelog <https://keepachangelog.com/en/1.0.0/>`__.

Unreleased
----------

* Added :class:`~swxsoc_reach.track.trackbase.REACHTrack`, a container for L1C dosimeter track data.
* Added :class:`~swxsoc_reach.geomap.geomapbase.GenericGeoMap`, a SunPy-like gridded geospatial map container with per-statistic/per-flavor data access.
* Added the :class:`~swxsoc_reach.util.enums.Flavor`, :class:`~swxsoc_reach.util.enums.SensorId`, and :class:`~swxsoc_reach.util.enums.Region` enumerations.
* Added the ``swxsoc_reach.util.geom`` module of region-geometry utilities to build, save, and load region contour paths.
* Added geomap plotting helpers to ``swxsoc_reach.visualization.viz`` using canonical ``Region`` colors and contour levels.
* Added the ``load_regions`` helper to ``swxsoc_reach.util.util`` to expose region longitudes, latitudes, and codes from the bundled contour data.
* Extended the processing pipeline so ``process_file`` converts L1C/CDF input into a combined geomap CDF plus per-flavor, per-statistic PNG plots.
* Added user guide pages for the constellation and enums (``constellation.rst``), region geometry (``geom.rst``), and the new map and track data objects (``data_objects.rst``).
* Added test coverage for the flavor/enum, geometry, geomap, track, and visualization modules.
* Project foundation and scaffolding were established, including the initial repository setup and template alignment.
* Update to support data pipeline, imports JSON files from UDL and outputs to CDF with ISTP-compliant metadata.
* Runtime and reliability improvements included temporary-path handling, logging improvements, and threaded UDL download support.
* Developer experience was improved through dependency updates, NumPy/doctest constraint refinements, formatting/test updates, and devcontainer/workflow maintenance.
* Documentation and release-readiness work expanded substantially, including docstring updates, Read the Docs/DOI integration, and new customization/changelog documentation.
* Updated docs build behavior to run Sphinx via the active Python environment (``python -m sphinx``) to avoid Homebrew executable conflicts.
* Fixed README badge definitions and URLs (GitHub Actions org links and coverage badge reStructuredText syntax).
* Added package version display to the About page using the Sphinx ``|release|`` substitution.
* Improved changelog discoverability from the docs landing page with a direct link.
