========
Overview
========

.. start-badges

.. list-table::
    :stub-columns: 1

    * - docs
      - |docs| |rtd|
    * - build status
      - |testing| |codestyle| |coverage|

.. |rtd| image:: https://readthedocs.org/projects/swxsoc-reach/badge/?version=latest
    :target: https://swxsoc-reach.readthedocs.io/en/latest/?badge=latest
    :alt: Readthedocs build status

.. |docs| image:: https://github.com/swxsoc/swxsoc_reach/actions/workflows/docs.yml/badge.svg
    :target: https://github.com/swxsoc/swxsoc_reach/actions/workflows/docs.yml
    :alt: self-build documentation status

.. |testing| image:: https://github.com/swxsoc/swxsoc_reach/actions/workflows/testing.yml/badge.svg
    :target: https://github.com/swxsoc/swxsoc_reach/actions/workflows/testing.yml
    :alt: testing status

.. |codestyle| image:: https://github.com/swxsoc/swxsoc_reach/actions/workflows/codestyle.yml/badge.svg
    :target: https://github.com/swxsoc/swxsoc_reach/actions/workflows/codestyle.yml
    :alt: codestyle and linting

.. |coverage| image:: https://codecov.io/gh/swxsoc/swxsoc_reach/graph/badge.svg?token=KHJfohC6yd
    :target: https://codecov.io/gh/swxsoc/swxsoc_reach
    :alt: code coverage

.. end-badges

A Python package by the NASA Space Weather Science Operations Center (SWxSOC) to get, process, and analyze data from the Responsive Environmental Assessment Commercially Hosted (REACH) dosimeters.
Built by the `Aerospace Corporation <https://aerospace.org/>`_ and flown on 32 Iridium NEXT spacecraft, REACH provides global, low-latency monitoring of space weather hazards, including total dose, internal charging, and single-event effects. 
Across the constellation, 64 dosimeters spanning six sensor types which together provide high-cadence global measurements of particle populations from about 100 keV to 2.5 MeV electrons and about 1 MeV to 50 MeV protons.

The REACH (Responsive Environmental Assessment Commercially Hosted) dosimeter network is an Air Force-led demonstration of 32 radiation-sensing 
payloads distributed across six orbital planes on Iridium NEXT satellites, designed to provide global space weather monitoring with less than 
20-minute revisit rates and 1-hertz sampling rates for rapidly detecting and characterizing radiation environments that could cause satellite 
anomalies or distinguish between natural space weather effects and hostile interference. The constellation includes multiple payload variants 
optimized for different measurement requirements: the standard payload configuration measures electrons from approximately 50 keV to 2 MeV and 
protons across comparable energy ranges using solid-state detector (SSD) based heads with spectral resolution capabilities, while a technology 
insertion of six low-energy payloads provides enhanced 50 keV detection sensitivity for characterizing the low-energy electron and proton 
environment critical for anomaly resolution in modern spacecraft. Each REACH dosimeter payload employs silicon semiconductor detectors that 
measure ionization energy loss as charged particles traverse the detector medium, converting the deposited energy into proportional electrical 
signals that are amplified and analyzed to determine particle flux, energy spectra, and accumulated radiation dose rates in real time. 
Specifically, the network utilizes mature micro-dosimeter technology developed by The Aerospace Corporation, based on heritage designs previously
flown on the AeroCube 6 mission. To measure the absorbed radiation dose, the instrument calculates the total ionizing energy deposited by these
traversing particles per unit mass of the active silicon volume, continuously integrating these discrete energy-loss events over time to yield
an accurate, cumulative exposure profile. These different flavors are achieved through the use of strategic material filters—including thin
aluminum foils, beryllium windows, and specialized absorbing materials positioned at different depths within the detector stack—that selectively
attenuate particles of specific energies, allowing the instrument to discriminate between different particle populations and energy ranges by
measuring transmission through multiple filter configurations and the resulting energy loss signatures.

Documentation
-------------
Documentation is available at https://swxsoc-reach.readthedocs.io/en/latest/

Data
----
REACH data is made available on NASA SPDF at https://spdf.gsfc.nasa.gov/pub/data/reach/dosimeter/l1c/all/. New data is made available every day with a data latency of ~2 days.

Acknowledgements
----------------
We would like to thank the `Aerospace Corporation <https://aerospace.org/>`_ for making these data available and for their support.
The package template used by this package is based on the one developed by the
`NASA Space Weather Science Operations Center (SWxSOC) <https://swxsoc.github.io>`_ which is based on those provided by
`OpenAstronomy community <https://openastronomy.org>`_ and the `SunPy Project <https://sunpy.org/>`_.

This project makes use of the `NASA Space Weather Science Operations Center (SWxSOC) <https://swxsoc.github.io>`_.
