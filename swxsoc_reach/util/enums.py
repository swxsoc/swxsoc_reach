"""REACH dosimeter flavor definitions."""

from __future__ import annotations

import re
from enum import Flag, auto


class Flavor(Flag):
    """REACH dosimeter channel (flavor) identifiers.

    Each member represents a distinct energy-threshold channel.
    Members are bitwise flags so they can be combined with ``|``.

    This is implemented with ``enum.Flag``.

    Examples
    --------
    >>> Flavor.W.label
    'W $\\geq$ 12 MeV $p^{+}$'
    >>> Flavor.from_str("w")
    <Flavor.W: 4>
    >>> Flavor.U | Flavor.W
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
