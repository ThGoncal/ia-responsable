"""Chargement d'une instance du concours et grandeurs dérivées."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

TYPES = "ntic"

Need = tuple[str, int, int]  # (type, lower, upper)


@dataclass
class Instance:
    """Une instance du concours, prête pour les algorithmes."""

    name: str
    text: str  # JSON brut, utilisé par le correcteur officiel
    energy_cap: int
    value: dict[int, int]
    energy: dict[int, int]
    needs: dict[int, list[Need]]
    size: dict[int, int]
    dtype: dict[int, str]
    copyrighted: dict[int, int]
    impossible: set[int] = field(init=False)
    lower: dict[int, dict[str, int]] = field(init=False)
    mono: dict[int, str] = field(init=False)
    free_supply: dict[str, int] = field(init=False)
    total_supply: dict[str, int] = field(init=False)

    def __post_init__(self) -> None:
        # Besoin impossible : upper < lower, aucun dataset ne peut le remplir, seule une source le peut.
        self.impossible = {m for m, needs in self.needs.items() if any(lo > hi for _, lo, hi in needs)}
        # Bornes basses des besoins remplissables, par modèle et par type.
        self.lower = {m: {t: lo for t, lo, hi in needs if lo <= hi} for m, needs in self.needs.items()}
        # Sources possibles : modèles à un seul besoin, remplissable.
        self.mono = {m: needs[0][0] for m, needs in self.needs.items() if len(needs) == 1 and m not in self.impossible}
        self.free_supply = {t: 0 for t in TYPES}
        self.total_supply = {t: 0 for t in TYPES}
        for d, s in self.size.items():
            self.total_supply[self.dtype[d]] += s
            if not self.copyrighted[d]:
                self.free_supply[self.dtype[d]] += s

    @property
    def energy_is_binding(self) -> bool:
        """Faux si tous les modèles réunis tiennent sous le plafond (contrainte redondante, cf. notebook 14)."""
        return sum(self.energy.values()) > self.energy_cap

    @property
    def data_is_scarce(self) -> bool:
        """Vrai si les modèles que l'énergie permet demanderaient plus de données que l'offre totale.

        Dans ce cas, les sources servent à économiser des données (notebooks 14 et 15)."""
        share = min(1.0, self.energy_cap / sum(self.energy.values()))
        demand = {t: sum(low.get(t, 0) for low in self.lower.values()) for t in TYPES}
        return any(demand[t] * share > self.total_supply[t] for t in TYPES)


def load(path: str | Path) -> Instance:
    """Charge un fichier d'instance JSON."""
    path = Path(path)
    text = path.read_text()
    raw = json.loads(text)
    return Instance(
        name=path.stem,
        text=text,
        energy_cap=raw["energyCap"],
        value={m["id"]: m["value"] for m in raw["models"]},
        energy={m["id"]: m["energyCost"] for m in raw["models"]},
        needs={
            m["id"]: [(t, b["lowerBound"], b["upperBound"]) for t, b in m["dataRequirements"].items()]
            for m in raw["models"]
        },
        size={d["id"]: d["size"] for d in raw["datasets"]},
        dtype={d["id"]: d["dataType"] for d in raw["datasets"]},
        copyrighted={d["id"]: d["isCopyrighted"] for d in raw["datasets"]},
    )
