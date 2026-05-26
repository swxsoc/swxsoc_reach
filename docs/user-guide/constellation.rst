.. _constellation-guide:

********************************
REACH Constellation & Enums
********************************

The REACH constellation consists of 32 sensors, one per satellite, each
carrying exactly two dosimeter channels whose energy-range "flavors" determine
what particle populations they measure.  The :mod:`swxsoc_reach.util.enums` module exposes
the authoritative Python representation of this constellation: three enumerations
and two utility functions backed by a bundled JSON mapping file.

.. contents:: On this page
   :local:
   :depth: 2

----

Enumerations
============

Flavor
------

Each :class:`~swxsoc_reach.util.enums.Flavor` member represents a distinct
energy-threshold dosimeter channel.  Because ``Flavor`` is an
:class:`enum.Flag`, individual flavors can be combined with ``|``:

See the full API description for :class:`swxsoc_reach.util.enums.Flavor` in
the :ref:`reference`.

.. doctest::

   >>> from swxsoc_reach.util.enums import Flavor
   >>> Flavor.W.label
   'W $\\geq$ 12 MeV $p^{+}$'
   >>> Flavor.from_str("w")
   <Flavor.W: 4>
   >>> Flavor.U | Flavor.W # doctest: +SKIP
   <Flavor.U|W: 5> 
   >>> Flavor.W in Flavor.ALL
   True

Energy thresholds
^^^^^^^^^^^^^^^^^

.. doctest::

      >>> from astropy.table import Table
      >>> from swxsoc_reach.util.enums import Flavor, sensor_ids_for_flavor
      >>> def _clean(lbl, name=""):
      ...     lbl = (lbl
      ...         .replace(r"$\geq$", ">=")
      ...         .replace(r"$e^{-}$", "e-")
      ...         .replace(r"$p^{+}$", "p+")
      ...         .replace("$", ""))
      ...     if name and lbl.startswith(name + " "):
      ...         lbl = lbl[len(name) + 1:]
      ...     return lbl
      >>> rows = [
      ...     (f.name, _clean(f.label, f.name), len(sensor_ids_for_flavor(f)))
      ...     for f in Flavor if f != Flavor.ALL
      ... ]
      >>> t = Table(rows=rows, names=["Flavor", "Energy threshold", "# Sensors"])
      >>> t.pprint_all()
      Flavor       Energy threshold      # Sensors
      ------ --------------------------- ---------
         U >= 5.0 MeV e-, >= 57 MeV p+         5
         V >= 3.4 MeV e-, >= 47 MeV p+         7
         W                >= 12 MeV p+        14
         X >= 360 keV e-, >= 12 MeV p+        20
         Y >= 1.6 MeV e-, >= 31 MeV p+        12
         Z >= 50 keV e-, >= 200 keV p+         6

SensorId
--------

``SensorId`` is also an :class:`enum.Flag`, so multiple satellites can be
addressed in a single expression:

See the full API description for :class:`swxsoc_reach.util.enums.SensorId` in
the :ref:`reference`.

.. doctest::

   >>> from swxsoc_reach.util.enums import SensorId
   >>> str(SensorId.REACH_101)
   'REACH-101'
   >>> SensorId.from_str("REACH-101")
   <SensorId.REACH_101: 1>
   >>> SensorId.from_str("101")
   <SensorId.REACH_101: 1>
   >>> SensorId.REACH_101 | SensorId.REACH_102 # doctest: +SKIP
   <SensorId.REACH_101|REACH_102: 3>

Region
------

``Region`` is a plain :class:`enum.Enum` whose members carry additional
metadata used for masking and plotting:

See the full API description for :class:`swxsoc_reach.util.enums.Region` in
the :ref:`reference`.

.. doctest::

   >>> from swxsoc_reach.util.enums import Region
   >>> Region.SAA.label
   'SAA and Inner Zone'
   >>> Region.SAA.color
   '#cd594a'
   >>> Region.SAA.code
   1
   >>> Region.ordered()  # doctest: +NORMALIZE_WHITESPACE
   (<Region.SAA: (0, 1, 'SAA and Inner Zone', 'saa', '#cd594a')>, <Region.POLAR_CAP: (1, 2, 'Polar Cap', 'polar_cap', '#efd469')>, <Region.OUTER_ZONE: (2, 3, 'Outer Zone', 'outer_zone', '#093145')>, <Region.SLOT: (3, 4, 'Slot', 'slot', '#b5c689')>)

----

Utility Functions
=================

.. autofunction:: swxsoc_reach.util.enums.load_reach_id_dosimeter_relationship
   :no-index:

.. autofunction:: swxsoc_reach.util.enums.sensor_ids_for_flavor
   :no-index:

Usage examples
--------------

.. doctest::

   >>> from swxsoc_reach.util.enums import (
   ...     Flavor,
   ...     SensorId,
   ...     load_reach_id_dosimeter_relationship,
   ...     sensor_ids_for_flavor,
   ... )
   >>> mapping = load_reach_id_dosimeter_relationship()
   >>> mapping[SensorId.REACH_169]
   (<Flavor.X: 8>, <Flavor.Z: 32>)
   >>> sensor_ids_for_flavor(Flavor.Z)  # doctest: +NORMALIZE_WHITESPACE
   [<SensorId.REACH_169: 8388608>, <SensorId.REACH_170: 16777216>, <SensorId.REACH_171: 33554432>, <SensorId.REACH_172: 67108864>, <SensorId.REACH_180: 1073741824>, <SensorId.REACH_181: 2147483648>]
   >>> len(sensor_ids_for_flavor("Flavor X"))
   20

.. note::

   The mapping is loaded from the bundled JSON file
   ``swxsoc_reach/data/reach_id_dosimeter_relationship.json`` the first time
   :func:`~swxsoc_reach.util.enums.load_reach_id_dosimeter_relationship` is
   called (automatically at package import time) and cached in memory
   thereafter.  Subsequent calls to
   :func:`~swxsoc_reach.util.enums.sensor_ids_for_flavor` do **not** re-read
   the file.

----

Constellation Overview
======================

The table below lists every REACH sensor and its two dosimeter flavors.

.. doctest::

   >>> from astropy.table import Table
   >>> from swxsoc_reach.util.enums import load_reach_id_dosimeter_relationship
   >>> mapping = load_reach_id_dosimeter_relationship()
   >>> rows = [
   ...     (str(sid), flavors[0].name, flavors[1].name)
   ...     for sid, flavors in mapping.items()
   ... ]
   >>> t = Table(rows=rows, names=["Sensor ID", "Dosimeter 1", "Dosimeter 2"])
   >>> t.pprint_all()
   Sensor ID Dosimeter 1 Dosimeter 2
   --------- ----------- -----------
   REACH-101           X           W
   REACH-102           Y           V
   REACH-105           Y           U
   REACH-108           X           W
   REACH-113           Y           V
   REACH-114           X           W
   REACH-115           X           W
   REACH-116           Y           V
   REACH-133           X           W
   REACH-134           Y           U
   REACH-135           X           W
   REACH-136           X           W
   REACH-137           X           W
   REACH-138           Y           U
   REACH-139           X           W
   REACH-140           Y           V
   REACH-148           Y           V
   REACH-149           X           W
   REACH-162           X           W
   REACH-163           Y           V
   REACH-164           X           W
   REACH-165           Y           U
   REACH-166           Y           V
   REACH-169           X           Z
   REACH-170           X           Z
   REACH-171           X           Z
   REACH-172           X           Z
   REACH-173           X           W
   REACH-175           Y           U
   REACH-176           X           W
   REACH-180           X           Z
   REACH-181           X           Z

Flavor statistics
-----------------

.. doctest::

      >>> from astropy.table import Table
      >>> from swxsoc_reach.util.enums import Flavor, sensor_ids_for_flavor
      >>> def _clean(lbl, name=""):
      ...     lbl = (lbl
      ...         .replace(r"$\geq$", ">=")
      ...         .replace(r"$e^{-}$", "e-")
      ...         .replace(r"$p^{+}$", "p+")
      ...         .replace("$", ""))
      ...     if name and lbl.startswith(name + " "):
      ...         lbl = lbl[len(name) + 1:]
      ...     return lbl
      >>> rows = []
      >>> for f in (f for f in Flavor if f != Flavor.ALL):
      ...     sensors = sensor_ids_for_flavor(f)
      ...     ids = ", ".join(str(s).replace("REACH-", "") for s in sensors)
      ...     rows.append((f.name, _clean(f.label, f.name), len(sensors), ids))
      >>> t = Table(rows=rows, names=["Flavor", "Energy threshold", "# Sensors", "Sensor IDs"])
      >>> t.pprint_all()  # doctest: +NORMALIZE_WHITESPACE
      Flavor       Energy threshold      # Sensors                                             Sensor IDs
      ------ --------------------------- --------- --------------------------------------------------------------------------------------------------
         U >= 5.0 MeV e-, >= 57 MeV p+         5                                                                            105, 134, 138, 165, 175
         V >= 3.4 MeV e-, >= 47 MeV p+         7                                                                  102, 113, 116, 140, 148, 163, 166
         W                >= 12 MeV p+        14                               101, 108, 114, 115, 133, 135, 136, 137, 139, 149, 162, 164, 173, 176
         X >= 360 keV e-, >= 12 MeV p+        20 101, 108, 114, 115, 133, 135, 136, 137, 139, 149, 162, 164, 169, 170, 171, 172, 173, 176, 180, 181
         Y >= 1.6 MeV e-, >= 31 MeV p+        12                                         102, 105, 113, 116, 134, 138, 140, 148, 163, 165, 166, 175
         Z >= 50 keV e-, >= 200 keV p+         6                                                                       169, 170, 171, 172, 180, 181
