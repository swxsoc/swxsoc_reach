"""REACH dosimeter flavor definitions."""

from __future__ import annotations

from enum import StrEnum


class Flavor(StrEnum):
    """REACH dosimeter channel (flavor) identifiers.

    Each member represents a distinct energy-threshold channel.
    The value is the short flavor code used in files and metadata.

    This is implemented with ``enum.StrEnum``.

    Examples
    --------
    >>> Flavor.Q.label
    'Q $\\\\geq$ 50 keV $e^{-}$, $\\\\geq$ 200 keV $p^{+}$'
    >>> Flavor.from_str("w")
    <Flavor.W: 'W'>
    >>> Flavor("U")
    <Flavor.U: 'U'>
    """

    U = "U"
    V = "V"
    W = "W"
    X = "X"
    Y = "Y"
    Q = "Q"

    @property
    def label(self) -> str:
        """Human-readable particle energy threshold label."""
        labels = {
            Flavor.U: r"U $\geq$ 5.0 MeV $e^{-}$, $\geq$ 57 MeV $p^{+}$",
            Flavor.V: r"V $\geq$ 3.4 MeV $e^{-}$, $\geq$ 47 MeV $p^{+}$",
            Flavor.W: r"W $\geq$ 12 MeV $p^{+}$",
            Flavor.X: r"X $\geq$ 360 keV $e^{-}$, $\geq$ 12 MeV $p^{+}$",
            Flavor.Y: r"Y $\geq$ 1.6 MeV $e^{-}$, $\geq$ 31 MeV $p^{+}$",
            Flavor.Q: r"Q $\geq$ 50 keV $e^{-}$, $\geq$ 200 keV $p^{+}$",
        }
        return labels[self]

    @classmethod
    def from_str(cls, name: str) -> "Flavor":
        """Return the ``Flavor`` member matching *name* (case-insensitive).

        Parameters
        ----------
        name : str
            Single-character flavor letter (e.g. ``"u"``, ``"W"``).

        Raises
        ------
        ValueError
            If *name* does not match any known flavor.
        """
        try:
            return cls.__members__[name.upper()]
        except KeyError:
            valid = ", ".join(cls.__members__)
            raise ValueError(
                f"Unknown flavor {name!r}. Must be one of: {valid}"
            ) from None
