.. _retrieving_data:

**********************************
Accessing & Downloading REACH Data
**********************************

Introduction
============

REACH dosimeter data can be accessed from two different archives, each served by its
own client:

- The :class:`~swxsoc_reach.net.REACHClient` searches and downloads REACH data hosted on
  the `Space Physics Data Facility (SPDF) <https://spdf.gsfc.nasa.gov/>`__ file server.
  It integrates directly with SunPy's :class:`~sunpy.net.fido_factory.UnifiedDownloaderFactory`
  (``Fido``) interface.
- The generic :class:`~swxsoc.net.client.SWXSOCClient` searches and downloads the more
  recent REACH data staged in the SWxSOC AWS S3 buckets. Because its ``search`` signature
  is not fully compatible with the SunPy ``Fido`` client interface, it is called directly
  rather than through ``Fido``.

Which client should I use?
---------------------------

- Use the :class:`~swxsoc_reach.net.REACHClient` for the **public archival record**,
  including the full historical mission and legacy NetCDF products.
- Use the :class:`~swxsoc.net.client.SWXSOCClient` for the **most recent data** produced
  by the SWxSOC processing pipeline before it is mirrored to SPDF. This client requires
  AWS access (see below).


REACHClient (SPDF)
==================

The :class:`~swxsoc_reach.net.REACHClient` registers itself with ``Fido`` when it is
imported. Importing it also makes the REACH-specific search attributes available:

.. code-block:: python

    from sunpy.net import Fido
    from sunpy.net import attrs as a

    from swxsoc_reach.net import REACHClient, DataType, Vehicle

Search attributes
-----------------

The following attributes are supported:

- ``a.Time`` -- the time range for the data (e.g., ``a.Time("2025-05-01", "2025-05-05")``).
  REACH files on SPDF are organized by year, so a request spanning multiple years searches
  each year's directory.
- ``a.Source`` -- the mission (use ``a.Source.reach``).
- ``a.Instrument`` -- the instrument (use ``a.Instrument.dosimeter``).
- ``a.Level`` -- the data processing level (use ``a.Level.l1c``).
- ``DataType`` -- the data type (e.g., ``DataType.prelim`` for preliminary data downloaded
  from the UDL). This applies to the multi-satellite ``all_satellites`` products.
- ``Vehicle`` -- the REACH vehicle. Use ``Vehicle.all_satellites`` for the combined
  multi-satellite products, or a single-satellite attribute such as ``Vehicle.vid_136_nc``.

Examples for searching data
---------------------------

Example 1: Searching combined (all-satellite) data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To search the combined multi-satellite dosimeter products:

.. code-block:: python

    results = Fido.search(
        a.Time("2025-05-01", "2025-05-05")
        & a.Source.reach
        & a.Instrument.dosimeter
        & Vehicle.all_satellites
    )
    results

Example 2: Searching the last few days of data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To search a rolling window of recent data:

.. code-block:: python

    import astropy.units as u
    from astropy.time import Time

    today = Time.now()
    five_days_ago = today - 5 * u.day
    results = Fido.search(
        a.Time(five_days_ago, today)
        & a.Source.reach
        & a.Instrument.dosimeter
        & Vehicle.all_satellites
    )
    results

Example 3: Searching data for a single satellite
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To search the products for a single REACH vehicle:

.. code-block:: python

    results = Fido.search(
        a.Time("2019-05-01", "2019-05-05")
        & a.Source.reach
        & a.Instrument.dosimeter
        & Vehicle.vid_136_nc
    )
    results

Example 4: Searching legacy NetCDF data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Older REACH data is available as legacy NetCDF (``.nc``) files. These are discovered
automatically alongside the modern CDF products:

.. code-block:: python

    results = Fido.search(
        a.Time("2018-05-01", "2018-05-05")
        & a.Source.reach
        & a.Instrument.dosimeter
    )
    results

Downloading data
----------------

After a search, download the files using the standard ``Fido`` interface:

.. code-block:: python

    import tempfile

    with tempfile.TemporaryDirectory() as temp_dir:
        downloaded_files = Fido.fetch(results, path=temp_dir)
    downloaded_files

You can also specify a permanent location for the files:

.. code-block:: python

    downloaded_files = Fido.fetch(results, path="./my_data_dir/")


SWXSOCClient (AWS S3)
=====================

The generic :class:`~swxsoc.net.client.SWXSOCClient` searches the SWxSOC AWS S3 buckets
for the most recent REACH data. It requires AWS credentials to the SWxSOC AWS S3 buckets.
Without them the client falls back to unsigned, public access where available.

.. note::

    When using ``swxsoc_reach``, the ``SWXSOC_MISSION`` environment variable is set to
    ``swxsoc_pipeline`` on import, which points the client at the correct S3 buckets. If
    you import the client on its own, set ``SWXSOC_MISSION`` first.

Search attributes
-----------------

The :class:`~swxsoc.net.client.SWXSOCClient` uses its own set of attributes, combined with
:class:`~sunpy.net.attr.AttrAnd`:

- ``SearchTime`` -- the time range (``SearchTime(start=..., end=...)`` using
  :class:`~astropy.time.Time` objects).
- ``Instrument`` -- the instrument name (e.g., ``Instrument("reach")``).
- ``Level`` -- the data level (e.g., ``Level("l1c")``).
- ``Descriptor`` -- optional data type / descriptor filter.
- ``DevelopmentBucket`` -- optional boolean; if ``True``, searches the development buckets.

Example: Searching AWS for recent data
--------------------------------------

.. code-block:: python

    from astropy.time import Time

    from swxsoc.net.client import SWXSOCClient
    from swxsoc.net.attr import AttrAnd, SearchTime, Level, Instrument

    client = SWXSOCClient()
    query = AttrAnd(
        [
            SearchTime(
                start=Time("2026-07-10T00:00:00"),
                end=Time("2026-07-11T00:00:00"),
            ),
            Instrument("reach"),
            Level("l1c"),
        ]
    )
    results = client.search(query)
    results

Downloading data
----------------

The AWS client downloads files using a :class:`parfive.Downloader`:

.. code-block:: python

    from parfive import Downloader

    downloader = Downloader()
    client.fetch(results, path="./my_data_dir/", downloader=downloader)
    downloaded_files = downloader.download()
    downloaded_files
