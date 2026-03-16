"""
REACH-specific schema metadata derivations.

Extends :class:`~swxsoc.util.schema.SWXSchema` with REACH-specific
global and variable attribute schema layers (YAML) and custom
derivation functions.

This follows the same pattern established by the HERMES mission
in ``hermes_core.util.schema.HermesDataSchema``.
"""

from pathlib import Path
from typing import Optional

from swxsoc.util.schema import SWXSchema

import swxsoc_reach
from swxsoc_reach.util.util import create_reach_filename

__all__ = ["REACHDataSchema"]

DEFAULT_GLOBAL_CDF_ATTRS_SCHEMA_FILE = "reach_default_global_cdf_attrs_schema.yaml"
DEFAULT_VARIABLE_CDF_ATTRS_SCHEMA_FILE = "reach_default_variable_cdf_attrs_schema.yaml"


class REACHDataSchema(SWXSchema):
    """
    Schema for REACH CDF data requirements and formatting.

    Layers REACH-specific global and variable attribute YAML schemas
    on top of the SWxSOC defaults.  Overrides derivation functions
    for ``Logical_source`` and ``Logical_file_id`` to produce
    REACH-appropriate values.

    Parameters
    ----------
    global_schema_layers : list[Path] or None, optional
        Additional global attribute schema files layered after the
        REACH defaults.
    variable_schema_layers : list[Path] or None, optional
        Additional variable attribute schema files layered after the
        REACH defaults.
    use_defaults : bool, optional
        Whether to include the SWxSOC/SAMMI base defaults (default *True*).
    """

    def __init__(
        self,
        global_schema_layers: Optional[list[Path]] = None,
        variable_schema_layers: Optional[list[Path]] = None,
        use_defaults: Optional[bool] = True,
    ):
        # REACH Default Global Schema
        global_schema_path = str(
            Path(swxsoc_reach.__file__).parent
            / "data"
            / DEFAULT_GLOBAL_CDF_ATTRS_SCHEMA_FILE
        )
        # REACH Default Variable Schema
        variable_schema_path = str(
            Path(swxsoc_reach.__file__).parent
            / "data"
            / DEFAULT_VARIABLE_CDF_ATTRS_SCHEMA_FILE
        )

        # Seed Layers with Defaults
        if not use_defaults:
            _global_schema_layers = []
            _variable_schema_layers = []
        else:
            _global_schema_layers = [global_schema_path]
            _variable_schema_layers = [variable_schema_path]

        # Extend any additional caller-supplied layers
        if global_schema_layers is not None and len(global_schema_layers) > 0:
            _global_schema_layers.extend(global_schema_layers)
        if variable_schema_layers is not None and len(variable_schema_layers) > 0:
            _variable_schema_layers.extend(variable_schema_layers)

        # Call SWxSOC Initialization to populate Schema
        super().__init__(
            global_schema_layers=_global_schema_layers,
            variable_schema_layers=_variable_schema_layers,
            use_defaults=use_defaults,
        )

    # =====================================================================
    #                   GLOBAL ATTRIBUTE DERIVATION STUBS
    # =====================================================================

    def _get_logical_source(self, data):
        """
        Derive the ``Logical_source`` global attribute for REACH.

        The logical source is the combination of the data source, data type, and instrument mode.

        Parameters
        ----------
        data : `~swxsoc.swxdata.SWXData`
            The assembled SWXData instance.

        Returns
        -------
        str
            ``Logical_source`` value.
        """
        attr_name = "Logical_source"
        if (attr_name not in data.meta) or (not data.meta[attr_name]):
            # Get Parts
            instrument_id = self._get_instrument_id(data)
            data_type = self._get_data_type(data)
            data_type_short_name, _ = data_type.split(">")
            instrument_mode = self._get_instrument_mode(data)

            # Build Derivation
            # reach_all_prelim
            logical_source = f"{instrument_id}_{instrument_mode}_{data_type_short_name}"
        else:
            logical_source = data.meta[attr_name]
        return logical_source

    def _get_logical_file_id(self, data):
        """
        Derive the ``Logical_file_id`` global attribute for REACH.

        The attribute stores the name of the CDF File without the file
        extension (e.g. '.cdf'). This attribute is requires to avoid
        loss of the originial source in case of renaming.

        Parameters
        ----------
        data : `~swxsoc.swxdata.SWXData`
            The assembled SWXData instance.

        Returns
        -------
        str
            ``Logical_file_id`` value (CDF filename without extension).
        """
        attr_name = "Logical_file_id"
        if (attr_name not in data.meta) or (not data.meta[attr_name]):
            # Get Parts
            start_time = self._get_start_time(data)
            data_level = self._get_data_level(data)
            version = self._get_version(data)
            mode = self._get_instrument_mode(data)
            data_type = self._get_data_type(data)
            data_type_short_name, _ = data_type.split(">")

            # Build Derivation
            science_filename = create_reach_filename(
                time=start_time,
                level=data_level,
                version=version,
                mode=mode,
                descriptor=data_type_short_name,
            )
            science_filename = science_filename.rstrip(
                swxsoc_reach.config["mission"]["file_extension"]
            )

        else:
            science_filename = data.meta[attr_name]
        return science_filename

    def _get_reach_version(self, data):
        """
        Return the ``swxsoc_reach`` package version used to generate the CDF.

        Parameters
        ----------
        data : `~swxsoc.swxdata.SWXData`
            The assembled SWXData instance.

        Returns
        -------
        str
            Package version string.
        """
        attr_name = "REACH_version"
        if attr_name in data.meta and data.meta[attr_name]:
            return data.meta[attr_name]
        return swxsoc_reach.__version__
