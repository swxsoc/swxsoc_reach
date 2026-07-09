"""REACH dosimeter flavor definitions."""

from __future__ import annotations

import json
import re
from enum import Enum, Flag, auto
from pathlib import Path


class Region(Enum):
    """REACH region definitions shared across masking and plotting logic."""

    SAA = (0, 1, "SAA and Inner Zone", "saa", "#cd594a")
    POLAR_CAP = (1, 2, "Polar Cap", "polar_cap", "#efd469")
    OUTER_ZONE = (2, 3, "Outer Zone", "outer_zone", "#093145")
    SLOT = (3, 4, "Slot", "slot", "#b5c689")

    def __init__(
        self,
        mask_index: int,
        code: int,
        label: str,
        key: str,
        color: str,
    ) -> None:
        self.mask_index = mask_index
        self.code = code
        self.label = label
        self.key = key
        self.color = color

    @property
    def signed_codes(self) -> tuple[int, int]:
        """Return signed region-code family (positive and negative)."""
        return (self.code, -self.code)

    @classmethod
    def ordered(cls) -> tuple["Region", ...]:
        """Return regions in canonical mask-axis order."""
        return (cls.SAA, cls.POLAR_CAP, cls.OUTER_ZONE, cls.SLOT)

    @classmethod
    def contour_levels(cls) -> list[int]:
        """Return signed contour level order used for contour plotting."""
        levels = [-region.code for region in reversed(cls.ordered())]
        levels.extend([region.code for region in cls.ordered()])
        return levels

    @classmethod
    def contour_colors(cls) -> list[str]:
        """Return contour colors corresponding to contour_levels order."""
        color_by_code = {
            -cls.SLOT.code: "#6b7280",
            -cls.OUTER_ZONE.code: cls.OUTER_ZONE.color,
            -cls.POLAR_CAP.code: cls.POLAR_CAP.color,
            -cls.SAA.code: cls.SAA.color,
            cls.SAA.code: cls.SAA.color,
            cls.POLAR_CAP.code: cls.POLAR_CAP.color,
            cls.OUTER_ZONE.code: cls.OUTER_ZONE.color,
            cls.SLOT.code: cls.SLOT.color,
        }
        return [color_by_code[level] for level in cls.contour_levels()]


class Flavor(Flag):
    """REACH dosimeter channel (flavor) identifiers.

    Each member represents a distinct energy-threshold channel.
    Members are bitwise flags so they can be combined with ``|``.

    This is implemented with ``enum.Flag``.

    Examples
    --------
    >>> Flavor.W.label
    'W $\\\geq$ 12 MeV $p^{+}$'
    >>> Flavor.from_str("w")
    <Flavor.W: 4>
    >>> Flavor.U | Flavor.W # doctest: +SKIP
    <Flavor.U|W: 5>
    >>> Flavor.W in Flavor.ALL
    True
    """

    U = auto()
    V = auto()
    W = auto()
    X = auto()
    Y = auto()
    Z = auto()
    ALL = U | V | W | X | Y | Z

    @classmethod
    def ordered(cls) -> tuple["Flavor", ...]:
        """Return flavors in canonical axis order."""
        return (cls.U, cls.V, cls.W, cls.X, cls.Y, cls.Z)

    @property
    def label(self) -> str:
        """Human-readable particle energy threshold label."""
        labels = {
            Flavor.U: r"U $\geq$ 5.0 MeV $e^{-}$, $\geq$ 57 MeV $p^{+}$",
            Flavor.V: r"V $\geq$ 3.4 MeV $e^{-}$, $\geq$ 47 MeV $p^{+}$",
            Flavor.W: r"W $\geq$ 12 MeV $p^{+}$",
            Flavor.X: r"X $\geq$ 360 keV $e^{-}$, $\geq$ 12 MeV $p^{+}$",
            Flavor.Y: r"Y $\geq$ 1.6 MeV $e^{-}$, $\geq$ 31 MeV $p^{+}$",
            Flavor.Z: r"Z $\geq$ 50 keV $e^{-}$, $\geq$ 200 keV $p^{+}$",
            Flavor.ALL: r"All flavors $\geq$ 50 keV $e^{-}$, $\geq$ 200 keV $p^{+}$",
        }
        return labels[self]

    @classmethod
    def from_str(cls, name: str) -> "Flavor":
        """Return the ``Flavor`` member matching *name* (case-insensitive).

        Accepts either a bare flavor letter or a longer string containing
        ``"Flavor <letter>"`` (e.g. ``"DOSE1 (Flavor X) in rad/second"``).

        Parameters
        ----------
        name : str
            A single-character flavor letter (e.g. ``"w"``) **or** a string
            containing ``"Flavor <letter>"`` (e.g. ``"DOSE1 (Flavor X) in rad/second"``).

        Raises
        ------
        ValueError
            If *name* does not match any known flavor.
        """
        # Try to extract flavor letter from "Flavor <X>" pattern first
        match = re.search(r"\bFlavor\s+([A-Za-z])\b", name)
        key = match.group(1) if match else name.strip()
        try:
            return cls.__members__[key.upper()]
        except KeyError:
            valid = ", ".join(cls.__members__)
            raise ValueError(
                f"Unknown flavor {name!r}. Must be one of: {valid}"
            ) from None

    def __str__(self):
        """
        returns human-readable flavor string, e.g. ``flavor-x`` instead of ``Flavor.X``.

        for `ALL` flavor, returns ``all`` instead of ``flavor-all``.
        """
        if self == Flavor.ALL:
            return "all"
        return super().__str__().replace("Flavor.", "flavor-")


class SensorId(Flag):
    """REACH sensor identifiers as combinable flags."""

    REACH_101 = auto()
    REACH_102 = auto()
    REACH_105 = auto()
    REACH_108 = auto()
    REACH_113 = auto()
    REACH_114 = auto()
    REACH_115 = auto()
    REACH_116 = auto()
    REACH_133 = auto()
    REACH_134 = auto()
    REACH_135 = auto()
    REACH_136 = auto()
    REACH_137 = auto()
    REACH_138 = auto()
    REACH_139 = auto()
    REACH_140 = auto()
    REACH_148 = auto()
    REACH_149 = auto()
    REACH_162 = auto()
    REACH_163 = auto()
    REACH_164 = auto()
    REACH_165 = auto()
    REACH_166 = auto()
    REACH_169 = auto()
    REACH_170 = auto()
    REACH_171 = auto()
    REACH_172 = auto()
    REACH_173 = auto()
    REACH_175 = auto()
    REACH_176 = auto()
    REACH_180 = auto()
    REACH_181 = auto()
    ALL = (
        REACH_101
        | REACH_102
        | REACH_105
        | REACH_108
        | REACH_113
        | REACH_114
        | REACH_115
        | REACH_116
        | REACH_133
        | REACH_134
        | REACH_135
        | REACH_136
        | REACH_137
        | REACH_138
        | REACH_139
        | REACH_140
        | REACH_148
        | REACH_149
        | REACH_162
        | REACH_163
        | REACH_164
        | REACH_165
        | REACH_166
        | REACH_169
        | REACH_170
        | REACH_171
        | REACH_172
        | REACH_173
        | REACH_175
        | REACH_176
        | REACH_180
        | REACH_181
    )

    def __str__(self) -> str:
        """Human-readable sensor id string, e.g. ``REACH-101``."""
        return self.name.replace("_", "-")

    @classmethod
    def from_str(cls, name: str | int) -> "SensorId":
        """Return the ``SensorId`` member matching *name*.

        Accepts values like ``"REACH-101"``, ``"reach_101"``, or ``"101"``.
        """
        if isinstance(name, int):
            if 0 > name or name >= 32:
                raise ValueError(
                    f"Invalid sensor index, must be non-negative and less than 32, got {name}."
                )
            reach_index = 2**name
            return cls(reach_index)
        else:
            cleaned = name.strip().upper().replace("-", "_")
            if cleaned.isdigit():
                cleaned = f"REACH_{cleaned}"
            elif not cleaned.startswith("REACH_"):
                cleaned = f"REACH_{cleaned.removeprefix('REACH')}"

            try:
                return cls.__members__[cleaned]
            except KeyError:
                raise ValueError(f"Unknown sensor id {name!r}.") from None

    def to_index(self) -> int:
        """Convert this sensor id flag to a zero-based index (e.g. REACH_101 -> 0)."""
        if self.value == 0 or self.value & (self.value - 1) != 0:
            raise ValueError(f"SensorId {self} is not a single valid sensor flag.")
        return self.value.bit_length() - 1


_RELATIONSHIP_CACHE: dict["SensorId", tuple["Flavor", ...]] | None = None


def load_reach_id_dosimeter_relationship(
    file_path: str | Path | None = None,
    *,
    force_reload: bool = False,
) -> dict[SensorId, tuple[Flavor, ...]]:
    """Load REACH-to-dosimeter mapping JSON as enum-typed dictionary.

    This function uses a module-level cache as a singleton configuration
    source. By default it reads from disk only once per Python process.

    Parameters
    ----------
    file_path : str or pathlib.Path, optional
        Path to the mapping JSON file. When ``None``, uses the package default
        ``swxsoc_reach/data/reach_id_dosimeter_relationship.json``.
    force_reload : bool, optional
        When ``True``, re-read from disk even if cached. Default is ``False``.

    Returns
    -------
    dict[SensorId, tuple[Flavor, ...]]
        Mapping from :class:`SensorId` to an ordered tuple of :class:`Flavor`
        values.
    """
    global _RELATIONSHIP_CACHE

    # Singleton-style fast path: default configuration is loaded once.
    if file_path is None and not force_reload and _RELATIONSHIP_CACHE is not None:
        return _RELATIONSHIP_CACHE

    path = (
        Path(file_path)
        if file_path is not None
        else Path(__file__).resolve().parents[1]
        / "data"
        / "reach_id_dosimeter_relationship.json"
    )

    with path.open(encoding="utf-8-sig") as f:
        raw: dict[str, dict[str, list[str]]] = json.load(f)

    mapping = {
        SensorId.from_str(sensor_id): tuple(
            Flavor.from_str(flavor_name) for flavor_name in payload["dosimeters"]
        )
        for sensor_id, payload in raw.items()
    }

    # Maintain a single shared in-memory mapping.
    _RELATIONSHIP_CACHE = mapping
    return mapping


def sensor_ids_for_flavor(flavor: Flavor | str) -> list[SensorId]:
    """Return all sensor IDs that include the requested flavor.

    Parameters
    ----------
    flavor : Flavor or str
        Target flavor to match. Strings are parsed with
        :meth:`Flavor.from_str`.

    Returns
    -------
    list[SensorId]
        Sensor IDs that contain ``flavor`` in their dosimeter list.
    """
    target = Flavor.from_str(flavor) if isinstance(flavor, str) else flavor
    mapping = load_reach_id_dosimeter_relationship()

    return [
        sensor_id for sensor_id, dosimeters in mapping.items() if target in dosimeters
    ]
