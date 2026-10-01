"""Core library for ops_reach.

This is a library of `pysat` instrument modules and methods designed to support
REACH instruments for conversion of level 1b data to level 1c.

"""

import os
import pkg_resources

from ops_reach import instruments  # noqa F401

# set version
__here__ = os.path.abspath(os.path.dirname(__file__))
__version__ = pkg_resources.get_distribution('ops_reach').version
