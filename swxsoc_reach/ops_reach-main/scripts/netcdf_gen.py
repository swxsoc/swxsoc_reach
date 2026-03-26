"""Sample script to generate netCDF versions of l1b files."""

import os

import ops_reach
from ops_reach.instruments import aero_reach
import pysat

export = True

labels = ['dose1', 'proton_flux1', 'electron_flux1',
          'dose2', 'proton_flux2', 'electron_flux2',
          'hk_15v_monitor', 'hk_5v_monitor', 'hk_3_3v_monitor',
          'blocal', 'bmin', 'k_sqrt', 'hmin']

max_val = {tag: -10 for tag in labels}
min_val = {tag: 1e10 for tag in labels}

# Figure out directory for final files
path = os.path.join(pysat.params['data_dirs'][0], 'aero', 'reach', 'l1c')
if not os.path.isdir(path):
    os.mkdir(path)

sum_files = 0
for inst_id in aero_reach.iids:
    # Generate main reach instrument
    reach = pysat.Instrument(inst_module=aero_reach, tag='l1b', inst_id=inst_id,
                             use_header=True)

    sum_files += len(reach.files.files)
    for date in reach.files.files.index:
        # Generate outfile name
        fname = aero_reach.fname['l1c'].format(datestr=aero_reach.datestr,
                                               inst_id=inst_id)

        # Get data
        reach.load(date=date, use_header=True)

        for var_name in labels:
            ind = reach[var_name] > -1e30
            if max_val[var_name] < reach[var_name].max():
                max_val[var_name] = reach[var_name].max()
            if min_val[var_name] > reach[var_name][ind].min():
                min_val[var_name] = reach[var_name][ind].min()

        if export:

            # Set export file name
            version = int(reach.meta.header.Data_version)
            outfile = os.path.join(path, inst_id, fname.format(year=date.year,
                                                               month=date.month,
                                                               day=date.day,
                                                               version=version))
            # Change HK 5V monitor to float
            reach['hk_5v_monitor'] = reach['hk_5v_monitor'].astype(float)

            # Update meta info for l1c
            reach.meta.header.Data_product = 'l1c'
            reach.meta.header.Logical_source = 'reach-vid-101_dosimeter-l1c'
            reach.meta.header.Software_version = ops_reach.__version__

            # Use meta translation table to include SPDF preferred format.
            # Note that multiple names are output for compliance with pysat.
            # Using the most generalized form for labels for future compatibility.
            meta_dict = {reach.meta.labels.min_val: ['VALIDMIN'],
                         reach.meta.labels.max_val: ['VALIDMAX'],
                         reach.meta.labels.units: ['UNITS'],
                         reach.meta.labels.name: ['CATDESC', 'LABLAXIS', 'FIELDNAM'],
                         reach.meta.labels.notes: ['VAR_NOTES'],
                         reach.meta.labels.fill_val: ['_FillValue'],
                         'Depend_0': ['DEPEND_0'],
                         'Format': ['FORMAT'],
                         'Monoton': ['MONOTON'],
                         'Var_Type': ['VAR_TYPE']}

            # Ouput data
            pysat.utils.io.inst_to_netcdf(reach, outfile, epoch_name='Epoch',
                                          meta_translation=meta_dict,
                                          export_pysat_info=False,
                                          zlib=True, complevel=6)
