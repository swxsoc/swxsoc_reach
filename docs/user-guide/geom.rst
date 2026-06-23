.. _geom-guide:

*********************
Geometry Region Guide
*********************

The :mod:`swxsoc_reach.util.geom` module provides geometry helpers for REACH
region boundaries.

Region Plots
============

The figure below reproduces the per-region contour visualization workflow used
in the development notebook, with one panel per region code.

.. plot::
   :include-source: True

   import matplotlib.pyplot as plt
   import numpy as np

   from swxsoc_reach.util.geom import REGION_CODES, read_contour_path
   from swxsoc_reach.util.util import load_regions
   
   lon_values, lat_values, region_grid = load_regions()
   ordered_codes = sorted(REGION_CODES)

   fig, axes = plt.subplots(2, 4, figsize=(16, 7), sharex=True, sharey=True)
   axes = axes.ravel()

   for ax, code in zip(axes, ordered_codes, strict=False):
       mask = region_grid == code
       if np.any(mask):
           ax.scatter(
               lon_values[mask],
               lat_values[mask],
               s=2,
               alpha=0.6,
               color="tab:blue",
               label="Region Samples",
           )
       
       path = read_contour_path()
       vertices = np.asarray(path.vertices, dtype=float)
       if vertices.shape[0] < 2:
           continue
       ax.plot(vertices[:, 0], vertices[:, 1], color="tab:red", linewidth=1.2)

       ax.set_title(f"{code}: {REGION_CODES[code]}")
       ax.set_xlim(-180, 180)
       ax.set_ylim(-90, 90)
       ax.grid(True, alpha=0.2)

   axes[0].set_ylabel("Latitude")
   axes[4].set_ylabel("Latitude")
   for axis in axes[4:]:
       axis.set_xlabel("Longitude")

   fig.suptitle("REACH Region Samples and Contour Paths", fontsize=14)
   fig.tight_layout()
