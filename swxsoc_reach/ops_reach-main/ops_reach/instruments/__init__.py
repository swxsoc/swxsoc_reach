# -*- coding: utf-8 -*-
"""Collection of instruments for the ops_reach library.

Each instrument is contained within a subpackage of this set.

"""

__all__ = ['aero_reach']

for inst in __all__:
    exec("from ops_reach.instruments import {x}".format(x=inst))

# Remove dummy variable
del inst
