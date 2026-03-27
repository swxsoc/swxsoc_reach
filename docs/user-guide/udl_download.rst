.. _udl_download:

*******************
UDL Data Download
*******************

This guide shows how to download REACH observations from UDL using
``swxsoc_reach.net.udl.download_UDL_reach_to_file``.

The public downloader API is synchronous. Internally, chunk requests are
executed concurrently using ``asyncio``.

Constraint: do not call this function from a thread where an asyncio event
loop is already running.

Function Summary
================

``download_UDL_reach_to_file``
  Downloads UDL chunk windows concurrently, combines all returned records,
  and writes one output file (JSON or CSV).

Parameters
==========

- ``auth_token``: UDL authorization token for the ``Authorization`` header.
- ``sensor_id``: REACH sensor identifier (for example ``REACH-1``) or ``ALL``.
- ``descriptor``: UDL descriptor value.
- ``output_format``: ``json`` or ``csv``.
- ``delay_seconds``: seconds subtracted from current time for query end.
- ``window_seconds``: total query duration in seconds.
- ``output_dir``: destination folder for the combined file.

Returns
=======

A ``pathlib.Path`` for the output file.

Notebook Example
================

.. code-block:: python

   from swxsoc_reach.net.udl import download_UDL_reach_to_file

    output_path = download_UDL_reach_to_file(
       auth_token="Bearer <token>",
       sensor_id="REACH-1",
       descriptor="electron",
       output_format="json",
       delay_seconds=300,
       window_seconds=3600,
       output_dir="./data",
   )

   print(output_path)

Script Example
==============

.. code-block:: python

   from swxsoc_reach.net.udl import download_UDL_reach_to_file

   def main() -> None:
       output_path = download_UDL_reach_to_file(
           auth_token="Bearer <token>",
           sensor_id="REACH-1",
           descriptor="electron",
           output_format="csv",
           delay_seconds=300,
           window_seconds=3600,
           output_dir="./data",
       )
       print(output_path)

   if __name__ == "__main__":
       main()

Errors
======

- ``ValueError`` is raised if ``output_format`` is not ``json`` or ``csv``.
- ``requests.HTTPError`` is raised if any UDL request fails.
