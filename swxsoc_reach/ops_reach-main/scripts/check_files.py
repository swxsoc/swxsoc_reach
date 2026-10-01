"""Check if l1c files exist for each l1b day."""

import numpy as np

from ops_reach.instruments import aero_reach
import pysat

total_file_diff = 0
total_files = 0

for inst_id in aero_reach.iids:
    # Generate main reach instrument
    l1b = pysat.Instrument(inst_module=aero_reach, tag='l1b', inst_id=inst_id,
                           use_header=True)
    l1c = pysat.Instrument(inst_module=aero_reach, tag='l1c', inst_id=inst_id,
                           use_header=True)

    if len(l1b.files.files) == len(l1c.files.files):
        check = np.all(l1b.files.files.index == l1c.files.files.index)
        file_diff = 0
    else:
        check = False
        file_diff = len(l1b.files.files) - len(l1c.files.files)

    print(inst_id, check, file_diff)
    total_file_diff += file_diff
    total_files += len(l1b.files.files)

print('\n{:} files left'.format(total_file_diff))
print('\n{:} total files'.format(total_files))
